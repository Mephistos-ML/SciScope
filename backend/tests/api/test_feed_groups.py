"""Grouped Feed HTTP contracts against SQLite and production PostgreSQL."""

import base64
from dataclasses import replace
from datetime import timedelta
import json

from fastapi.testclient import TestClient
import pytest

from app.api.app import app
from app.config import AUTH_SESSION_COOKIE_NAME
from app.services.auth.service import create_authenticated_session
from app.storage.auth.users import create_user
from app.storage.feed.events import get_feed_event_for_user, mark_feed_event_read_for_user
from app.storage.feed.groups import publish_feed_update_groups
from tests.fixtures.database import build_test_database_url, migrate_test_database
from tests.fixtures.feed import feed_event, feed_group


@pytest.fixture(params=("sqlite", pytest.param("postgres", marks=pytest.mark.postgres)))
def feed_api(request, tmp_path, monkeypatch):
    url = request.getfixturevalue("postgres_url") if request.param == "postgres" else build_test_database_url(tmp_path / "groups.sqlite3")
    if request.param == "sqlite":
        migrate_test_database(url)
    monkeypatch.setattr(app.state, "database_url", url)
    for user_id in ("user-1", "other"):
        create_user(user_id=user_id, email=f"{user_id}@example.com", display_name=user_id, database_url=url)
    with TestClient(app) as client:
        token = create_authenticated_session("user-1", database_url=url, ttl_seconds=3600)
        client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
        yield client, url


def publish(url, *events, key="scan-1"):
    group = feed_group(*events, publication_key=key)
    publish_feed_update_groups(events, (group,), database_url=url)
    return group


def test_card_pagination_uses_activity_not_member_count_or_scan_time(feed_api):
    client, url = feed_api
    base = feed_event()
    commits = tuple(replace(feed_event(f"commit:{index}"), published_at=base.published_at + timedelta(hours=2)) for index in range(23))
    first = publish(url, *commits)
    release = replace(feed_event("release:one", kind="release"), published_at=base.published_at + timedelta(hours=1))
    # The release timestamp controls its card, not its commit or publication time.
    later_commit = replace(feed_event("commit:release"), published_at=base.published_at + timedelta(hours=3))
    second = publish(url, release, later_commit, key="release-one")
    undated = replace(feed_event("commit:undated"), published_at=None, created_at=base.created_at + timedelta(days=1))
    third = publish(url, undated, key="scan-undated")
    fourth = publish(url, replace(feed_event("commit:also-undated"), published_at=None,
                                  created_at=undated.created_at), key="scan-also-undated")
    response = client.get("/api/feed/groups", params={"limit": 1})
    assert response.status_code == 200
    page = response.json()
    assert [item["groupId"] for item in page["items"]] == [first.group_id]
    assert page["items"][0]["commitCount"] == 23
    assert page["unreadCount"] == 4
    assert page["hasMore"] is True
    newer = replace(feed_event("commit:newer"), published_at=base.published_at + timedelta(hours=4))
    publish(url, newer, key="scan-newer")
    ids = [first.group_id]
    while page["nextCursor"]:
        response = client.get("/api/feed/groups", params={"limit": 1, "cursor": page["nextCursor"]})
        assert response.status_code == 200
        page = response.json()
        ids.extend(item["groupId"] for item in page["items"])
    assert ids == [first.group_id, second.group_id, *sorted((third.group_id, fourth.group_id), reverse=True)]
    assert page["hasMore"] is False
    assert page["unreadCount"] == 5
    detail = client.get(f"/api/feed/groups/{second.group_id}").json()
    assert detail["title"] == release.title
    assert detail["release"]["rawText"] == release.raw_text
    assert [item["eventId"] for item in detail["commits"]] == [later_commit.event_id]


def test_commit_details_are_bounded_and_reading_requires_explicit_action(feed_api):
    client, url = feed_api
    events = tuple(feed_event(f"commit:{index}") for index in range(23))
    group = publish(url, *events)
    marked = mark_feed_event_read_for_user("user-1", events[0].event_id, database_url=url)
    first = client.get(f"/api/feed/groups/{group.group_id}").json()
    assert len(first["commits"]) == 10
    assert first["commitCount"] == 23
    assert first["unreadEventCount"] == 22
    assert first["isRead"] is False
    assert first["release"] is None
    page = first
    ids = []
    while True:
        ids.extend(item["eventId"] for item in page["commits"])
        if page["nextCursor"] is None:
            break
        response = client.get(f"/api/feed/groups/{group.group_id}", params={"cursor": page["nextCursor"]})
        assert response.status_code == 200
        page = response.json()
    assert len(ids) == len(set(ids)) == 23
    assert set(ids) == set(group.event_ids)
    assert client.get("/api/feed/groups?state=unread").json()["unreadCount"] == 1
    result = client.patch(f"/api/feed/groups/{group.group_id}")
    assert result.status_code == 200
    assert result.json()["isRead"] is True
    read_times = [get_feed_event_for_user("user-1", event.event_id, database_url=url).read_at for event in events]
    assert all(read_times)
    assert read_times[0] == marked.read_at
    assert client.patch(f"/api/feed/groups/{group.group_id}").status_code == 200
    assert [get_feed_event_for_user("user-1", event.event_id, database_url=url).read_at for event in events] == read_times
    assert client.get("/api/feed/groups?state=unread").json()["items"] == []
    assert client.get("/api/feed/groups").json()["unreadCount"] == 0


def test_ownership_subscription_filters_and_read_all_preserve_other_users(feed_api):
    client, url = feed_api
    own = publish(url, feed_event())
    another = publish(url, feed_event("commit:second", subscription_id="sub-2"), key="scan-two")
    foreign_event = feed_event("commit:foreign", user_id="other", subscription_id="foreign-sub")
    foreign = publish(url, foreign_event)
    result = client.get("/api/feed/groups", params={"subscription_id": "sub-2"}).json()
    assert [item["groupId"] for item in result["items"]] == [another.group_id]
    assert result["unreadCount"] == 2  # The global card badge is independent of the filter.
    assert client.get("/api/feed/groups?subscription_id=foreign-sub").json()["items"] == []
    for method in (client.get, client.patch):
        for group_id in (foreign.group_id, "missing"):
            assert method(f"/api/feed/groups/{group_id}").status_code == 404
    assert get_feed_event_for_user("other", foreign_event.event_id, database_url=url).read_at is None
    assert client.post("/api/feed/read-all").status_code == 200
    assert client.get("/api/feed/groups").json()["unreadCount"] == 0
    assert client.get(f"/api/feed/groups/{own.group_id}").json()["isRead"] is True
    assert get_feed_event_for_user("other", foreign_event.event_id, database_url=url).read_at is None
    client.cookies.clear()
    for method, path in ((client.get, "/api/feed/groups"), (client.get, f"/api/feed/groups/{own.group_id}"),
                         (client.patch, f"/api/feed/groups/{own.group_id}")):
        assert method(path).status_code == 401


def test_cursor_validation_and_namespace_prevent_cross_group_paging(feed_api):
    client, url = feed_api
    group = publish(url, *(feed_event(f"commit:{index}") for index in range(12)))
    second = publish(url, feed_event("commit:second", subscription_id="sub-2"))
    list_cursor = client.get("/api/feed/groups?limit=1").json()["nextCursor"]
    detail_cursor = client.get(f"/api/feed/groups/{group.group_id}").json()["nextCursor"]
    assert client.get(f"/api/feed/groups/{second.group_id}", params={"cursor": detail_cursor}).status_code == 422
    assert client.get(f"/api/feed/groups/{group.group_id}", params={"cursor": list_cursor}).status_code == 422
    assert client.get("/api/feed/groups", params={"cursor": detail_cursor}).status_code == 422
    decoded = json.loads(base64.urlsafe_b64decode(list_cursor + "=" * (-len(list_cursor) % 4)))
    malformed = ["", "%%%", "a" * 2049]
    for payload in ([], {**decoded, "v": 2}, {**decoded, "createdAt": "2026-10-09T12:00:00"},
                    {**decoded, "publishedAt": 123}, {**decoded, "groupId": ""}):
        malformed.append(base64.urlsafe_b64encode(json.dumps(payload).encode()).decode())
    for cursor in malformed:
        assert client.get("/api/feed/groups", params={"cursor": cursor}).status_code == 422
    for params in ({"limit": 0}, {"limit": 51}, {"state": "invalid"}):
        assert client.get("/api/feed/groups", params=params).status_code == 422
    assert client.get(f"/api/feed/groups/{group.group_id}?limit=51").status_code == 422

"""Grouped Feed HTTP contracts against SQLite and production PostgreSQL."""

import base64
from dataclasses import replace
from datetime import timedelta
import json

from fastapi.testclient import TestClient
import pytest

from app.api.app import app
from app.models.feed import FeedReleaseCommitDetails, RELEASE_COMMIT_METADATA_KEY
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
    release = replace(release, metadata={**release.metadata, RELEASE_COMMIT_METADATA_KEY:
        FeedReleaseCommitDetails("complete", (later_commit.event_id,), "b" * 40, "a" * 40, 1).to_metadata()})
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


def test_monitoring_release_links_reuse_old_facts_and_commit_atomically(feed_api, monkeypatch):
    from sqlalchemy import update
    from app.database.records.feed import FeedEventRecordModel
    from app.database.session import session_scope
    from app.jobs.scan_subscriptions import run_repository_monitoring_scan
    from app.models.monitoring import RepositoryActivity, ReleaseCommitDetails
    from app.models.repository import Repository
    from app.models.signal import Signal
    from app.storage.feed.events import list_feed_events_for_user
    from app.storage.feed.groups import get_feed_update_group_for_user
    from app.storage.feed.retention import delete_feed_events_older_than
    from app.storage.monitoring import state
    from app.storage.repositories.repositories import upsert_repositories
    from app.storage.subscriptions.subscriptions import create_subscription
    from datetime import UTC, datetime

    client, url = feed_api
    repository = Repository("github:repo:123", "github", "science/tool", "https://github.com/science/tool")
    upsert_repositories((repository,), database_url=url)
    create_subscription(user_id="user-1", repository_id=repository.repository_id, selected_query=None, database_url=url)
    now = datetime.now(UTC) + timedelta(minutes=1)
    def signal(name, kind="commit", published_at=now):
        return Signal("github", kind, f"science/tool:{kind}:{name}", name, repository.url, published_at,
                      f"{name}\n\nCanonical content", payload={"repo": "science/tool", "tag_name": name} if kind == "release" else {"repo": "science/tool"})
    old = signal("old")
    added, unrelated = signal("added"), signal("unrelated", published_at=now + timedelta(minutes=2))
    detail_only = signal("detail-only", published_at=datetime(2000, 1, 1, tzinfo=UTC))
    release = signal("v2", "release", published_at=now + timedelta(minutes=1))
    activity = RepositoryActivity((old,), True, True, "old-head")
    calls = []
    class Monitor:
        def load_repository_activity(self, *args, **kwargs):
            return activity
        def load_release_commit_details(self, *args, **kwargs):
            calls.append(kwargs["deadline_monotonic"])
            return ReleaseCommitDetails("complete", (replace(old, title="Old tag context"), added, detail_only), "b" * 40, "a" * 40, 3)
        def refresh_repository_profile(self, profile):
            return profile
    monitor = Monitor()
    def run():
        run_repository_monitoring_scan(resolve_monitor=lambda _source: monitor, database_url=url)
    run()
    original = client.get("/api/feed/groups").json()["items"][0]
    old_group = get_feed_update_group_for_user("user-1", original["groupId"], database_url=url)
    old_event = list_feed_events_for_user("user-1", database_url=url)[0]
    marked = client.patch(f"/api/feed/{old_event.event_id}").json()["readAt"]
    create_subscription(user_id="other", repository_id=repository.repository_id, selected_query=None, database_url=url)
    activity = RepositoryActivity((release, added, unrelated), True, True, "new-head")
    before = state.get_repository_monitoring_cursors(repository.repository_id, database_url=url)
    with monkeypatch.context() as fault:
        original_write = state.write_feed_update_groups
        def fail(session, groups):
            original_write(session, groups)
            raise RuntimeError("Injected failure after release publication")
        fault.setattr(state, "write_feed_update_groups", fail)
        run()
    assert len(list_feed_events_for_user("user-1", database_url=url)) == 1
    assert list_feed_events_for_user("other", database_url=url) == []
    assert state.get_repository_monitoring_cursors(repository.repository_id, database_url=url) == before
    assert client.get("/api/feed/groups").json()["items"][0]["groupId"] == old_group.group_id
    run()
    cards = client.get("/api/feed/groups").json()
    assert cards["unreadCount"] == 2
    watched = client.get("/api/subscriptions").json()["items"]
    assert len(watched) == 1
    assert watched[0]["unreadGroupCount"] == 2
    assert watched[0]["unreadEventCount"] == 4
    assert len(cards["items"]) == 3
    assert get_feed_update_group_for_user("user-1", old_group.group_id, database_url=url) == old_group
    release_card = next(item for item in cards["items"] if item["kind"] == "release")
    detail = client.get(f"/api/feed/groups/{release_card['groupId']}").json()
    assert detail["commitDetailsStatus"] == "complete"
    assert detail["commitCount"] == detail["totalCommitCount"] == 3
    assert {item["title"] for item in detail["commits"]} == {"old", "added", "detail-only"}
    assert datetime.fromisoformat(next(item for item in detail["commits"] if item["title"] == "old")["readAt"]) == datetime.fromisoformat(marked)
    membership = get_feed_update_group_for_user("user-1", release_card["groupId"], database_url=url)
    assert len(membership.event_ids) == 3  # Release + two fresh facts; old stays in its original card.
    assert old_event.event_id not in membership.event_ids
    assert len(list_feed_events_for_user("user-1", database_url=url)) == 5
    assert len(list_feed_events_for_user("other", database_url=url)) == 5
    assert len(calls) == 2  # One comparison per repository attempt, shared by both subscriptions.
    # Re-fetching the release neither repeats enrichment nor loses its snapshot.
    run()
    assert len(calls) == 2
    assert client.get(f"/api/feed/groups/{release_card['groupId']}").json() == detail
    removed_ids = [item.event_id for user in ("user-1", "other")
                   for item in list_feed_events_for_user(user, database_url=url) if item.title == "detail-only"]
    with session_scope(url) as session:
        session.execute(update(FeedEventRecordModel).where(FeedEventRecordModel.event_id.in_(removed_ids))
                        .values(created_at=datetime(2000, 1, 1, tzinfo=UTC)))
    delete_feed_events_older_than(datetime(2020, 1, 1, tzinfo=UTC), database_url=url)
    retained = client.get(f"/api/feed/groups/{release_card['groupId']}").json()
    assert retained["commitDetailsStatus"] == "partial"
    assert retained["commitCount"] == 2 and retained["totalCommitCount"] == 3
    assert retained["hasMore"] is False
    assert client.patch(f"/api/feed/groups/{release_card['groupId']}").status_code == 200
    watched = client.get("/api/subscriptions").json()["items"][0]
    assert watched["unreadGroupCount"] == watched["unreadEventCount"] == 1


def test_unavailable_release_details_keep_the_release_link_without_fake_zero(feed_api):
    client, url = feed_api
    release = feed_event("release:unknown", kind="release")
    group = publish(url, release)
    response = client.get(f"/api/feed/groups/{group.group_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["commitDetailsStatus"] == "unavailable"
    assert payload["commitCount"] is None and payload["totalCommitCount"] is None
    assert payload["commits"] == [] and payload["hasMore"] is False
    assert payload["url"] == release.url and payload["release"]["rawText"] == release.raw_text


def test_unknown_persisted_release_version_is_a_data_failure_not_empty_coverage(feed_api):
    from sqlalchemy import update
    from app.database.records.feed import FeedEventRecordModel
    from app.database.session import session_scope
    client, url = feed_api
    release = feed_event("release:future", kind="release")
    group = publish(url, release)
    with session_scope(url) as session:
        session.execute(update(FeedEventRecordModel).where(FeedEventRecordModel.event_id == release.event_id)
                        .values(metadata_json={RELEASE_COMMIT_METADATA_KEY: {"v": 2}}))
    response = client.get(f"/api/feed/groups/{group.group_id}")
    assert response.status_code == 500
    assert response.json()["code"] == "persistence_failed"

"""Tests for durable feed-event persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.feed import FeedEvent
from app.storage.feed import (
    count_feed_events,
    get_feed_event_for_user,
    list_feed_events_for_user,
    upsert_feed_events,
)
from tests.conftest import build_test_database_url, migrate_test_database


def test_upsert_feed_events_persists_feed_rows(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "feed.sqlite3")
    migrate_test_database(database_url)
    created_at = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    published_at = datetime(2026, 8, 27, 11, 55, tzinfo=UTC)

    upsert_feed_events(
        (
            FeedEvent(
                event_id="sub_1:github:repo-a:release:1",
                user_id="user_1",
                subscription_id="sub_1",
                repository_id="github:repo:repo-a",
                repository_full_name="org/repo-a",
                repository_source="github",
                repository_url="https://github.com/org/repo-a",
                selected_query="paramagnetic nmr",
                source="github",
                kind="release",
                item_id="org/repo-a:release:1",
                title="org/repo-a release v1.0.0",
                url="https://github.com/org/repo-a/releases/tag/v1.0.0",
                published_at=published_at,
                raw_text="v1.0.0\n\nAdds PCS fitting improvements.",
                normalized_text="org/repo-a release v1.0.0\nv1.0.0\nAdds PCS fitting improvements.",
                metadata={"repo": "org/repo-a"},
                created_at=created_at,
            ),
        ),
        database_url=database_url,
    )

    items = list_feed_events_for_user("user_1", database_url=database_url)

    assert len(items) == 1
    assert items[0].repository_full_name == "org/repo-a"
    assert items[0].kind == "release"
    assert count_feed_events(database_url=database_url) == 1


def test_get_feed_event_for_user_scopes_lookup(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "feed.sqlite3")
    migrate_test_database(database_url)

    event = FeedEvent(
        event_id="sub_1:github:repo-a:commit:abc",
        user_id="user_1",
        subscription_id="sub_1",
        repository_id="github:repo:repo-a",
        repository_full_name="org/repo-a",
        repository_source="github",
        repository_url="https://github.com/org/repo-a",
        selected_query="paramagnetic nmr",
        source="github",
        kind="commit",
        item_id="org/repo-a:commit:abc",
        title="org/repo-a commit abc1234",
        url="https://github.com/org/repo-a/commit/abc",
        published_at=datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
        raw_text="Refine PCS tensor fitting",
        normalized_text="Refine PCS tensor fitting",
        metadata={"repo": "org/repo-a"},
        created_at=datetime(2026, 8, 27, 12, 5, tzinfo=UTC),
    )
    upsert_feed_events((event,), database_url=database_url)

    assert (
        get_feed_event_for_user("user_1", event.event_id, database_url=database_url)
        is not None
    )
    assert (
        get_feed_event_for_user("user_2", event.event_id, database_url=database_url)
        is None
    )

"""Canonical Feed facts for publication and migration tests."""

from datetime import UTC, datetime

from app.models.feed import FeedEvent, FeedUpdateGroup, build_feed_event_id, build_feed_update_group_id


def feed_event(item_id="commit:one", *, kind="commit", user_id="user-1", subscription_id="sub-1"):
    return FeedEvent(
        event_id=build_feed_event_id(subscription_id, "github", item_id),
        user_id=user_id, subscription_id=subscription_id, repository_id="github:repo:123",
        repository_full_name="science/tool", repository_source="github",
        repository_url="https://github.com/science/tool", selected_query="simulation",
        source="github", kind=kind, item_id=item_id, title=item_id,
        url=f"https://github.com/science/tool/{item_id}",
        published_at=datetime(2026, 10, 9, 10, tzinfo=UTC), raw_text="Preserved content",
        normalized_text="preserved content", metadata={"fact": "preserved"},
        created_at=datetime(2026, 10, 9, 12, tzinfo=UTC),
    )


def feed_group(*events, publication_key="scan-1"):
    first = events[0]
    kind = "release" if first.kind == "release" else "commits"
    return FeedUpdateGroup(
        build_feed_update_group_id(first.subscription_id, kind, publication_key),
        first.user_id, first.subscription_id, first.repository_id, kind,
        tuple(event.event_id for event in events), first.created_at,
    )

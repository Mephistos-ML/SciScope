"""Publication policy for newly discovered subscription events."""

from collections.abc import Sequence
from datetime import datetime

from app.models.feed import FeedEvent, FeedUpdateGroup, FeedUpdateKind, build_feed_update_group_id


def build_feed_update_groups(
    events: Sequence[FeedEvent], *, publication_key: str, created_at: datetime,
) -> list[FeedUpdateGroup]:
    """Give each release a card and each subscription's scan commits one card."""
    subscriptions: dict[str, list[FeedEvent]] = {}
    for event in events:
        if event.kind not in {"release", "commit"}:
            raise ValueError("Unsupported feed event kind for publication.")
        subscriptions.setdefault(event.subscription_id, []).append(event)
    groups = []
    for subscription_id, items in subscriptions.items():
        batches: list[tuple[FeedUpdateKind, str, tuple[FeedEvent, ...]]] = [
            ("release", event.event_id, (event,)) for event in items if event.kind == "release"
        ]
        commits = tuple(event for event in items if event.kind == "commit")
        if commits:
            batches.append(("commits", publication_key, commits))
        for kind, key, members in batches:
            first = members[0]
            groups.append(FeedUpdateGroup(
                group_id=build_feed_update_group_id(subscription_id, kind, key),
                user_id=first.user_id, subscription_id=subscription_id,
                repository_id=first.repository_id, kind=kind,
                event_ids=tuple(event.event_id for event in members), created_at=created_at,
            ))
    return groups

"""Publication policy for newly discovered subscription events."""

from collections.abc import Sequence
from datetime import datetime

from app.models.feed import FeedEvent, FeedUpdateGroup, build_feed_update_group_id, read_feed_release_commit_details


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
        releases = [event for event in items if event.kind == "release"]
        commits = [event for event in items if event.kind == "commit"]
        claims: dict[str, list[str]] = {}
        for release in releases:
            for event_id in read_feed_release_commit_details(release.metadata).event_ids:
                claims.setdefault(event_id, []).append(release.event_id)
        related: dict[str, list[FeedEvent]] = {}
        remaining = []
        for commit in commits:
            owners = claims.get(commit.event_id, ())
            if len(owners) == 1:
                related.setdefault(owners[0], []).append(commit)
            else:
                remaining.append(commit)
        for release in releases:
            groups.append(FeedUpdateGroup(
                group_id=build_feed_update_group_id(subscription_id, "release", release.event_id),
                user_id=release.user_id, subscription_id=subscription_id,
                repository_id=release.repository_id, kind="release",
                event_ids=(release.event_id, *(event.event_id for event in related.get(release.event_id, ()))),
                created_at=created_at,
            ))
        if remaining:
            first = remaining[0]
            groups.append(FeedUpdateGroup(
                group_id=build_feed_update_group_id(subscription_id, "commits", publication_key),
                user_id=first.user_id, subscription_id=subscription_id,
                repository_id=first.repository_id, kind="commits",
                event_ids=tuple(event.event_id for event in remaining), created_at=created_at,
            ))
    return groups

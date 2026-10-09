"""Publication policy for newly discovered subscription events."""

from collections.abc import Sequence
from datetime import datetime

from app.models.feed import FeedEvent, FeedUpdateGroup, FeedUpdateKind, build_feed_update_group_id, read_feed_release_commit_details


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
        batches: list[tuple[FeedUpdateKind, str, tuple[FeedEvent, ...]]] = [
            ("release", release.event_id, (release, *related.get(release.event_id, ())))
            for release in releases
        ]
        if remaining:
            batches.append(("commits", publication_key, tuple(remaining)))
        for kind, key, members in batches:
            first = members[0]
            groups.append(FeedUpdateGroup(
                group_id=build_feed_update_group_id(subscription_id, kind, key),
                user_id=first.user_id, subscription_id=subscription_id,
                repository_id=first.repository_id, kind=kind,
                event_ids=tuple(event.event_id for event in members), created_at=created_at,
            ))
    return groups

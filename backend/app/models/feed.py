"""Feed event domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from typing import Literal
from uuid import UUID, uuid5


FEED_EVENT_ID_NAMESPACE = UUID("e71b2aec-1284-582c-a932-f86ef904d44c")
FEED_UPDATE_GROUP_ID_NAMESPACE = UUID("fc1663e6-3c3d-4b77-8adc-70fbffb44c93")
FeedUpdateKind = Literal["release", "commits"]


def build_feed_update_group_id(
    subscription_id: str, kind: FeedUpdateKind, publication_key: str,
) -> str:
    """Identify a release or one scan publication independently of its display."""
    if not subscription_id or kind not in {"release", "commits"} or not publication_key:
        raise ValueError("A group requires a subscription, supported kind, and publication key.")
    return str(uuid5(FEED_UPDATE_GROUP_ID_NAMESPACE, "\x1f".join((subscription_id, kind, publication_key))))


@dataclass(frozen=True)
class FeedUpdateGroup:
    """An immutable publication of events for one user's repository subscription."""

    group_id: str
    user_id: str
    subscription_id: str
    repository_id: str
    kind: FeedUpdateKind
    event_ids: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not all((self.group_id, self.user_id, self.subscription_id, self.repository_id)):
            raise ValueError("Group identity and ownership are required.")
        if self.kind not in {"release", "commits"}:
            raise ValueError("Unsupported Feed update kind.")
        if not self.event_ids or not all(self.event_ids) or len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("A group requires a nonempty set of distinct event IDs.")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("Group creation time must include a timezone.")


def build_feed_event_id(subscription_id: str, source: str, item_id: str) -> str:
    """Build the stable opaque identity for one subscribed provider event."""

    return str(uuid5(FEED_EVENT_ID_NAMESPACE, "\x1f".join((subscription_id, source, item_id))))


@dataclass(frozen=True)
class FeedEvent:
    """One user-visible monitoring event kept in the durable feed."""

    event_id: str
    user_id: str
    subscription_id: str
    repository_id: str
    repository_full_name: str
    repository_source: str
    repository_url: str
    selected_query: str | None
    source: str
    kind: str
    item_id: str
    title: str
    url: str
    published_at: datetime | None
    raw_text: str
    normalized_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    read_at: datetime | None = None


@dataclass(frozen=True)
class FeedCursor:
    """Stable position in one user's reverse-chronological Feed."""

    published_at: datetime | None
    created_at: datetime
    event_id: str

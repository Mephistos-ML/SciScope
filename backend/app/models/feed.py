"""Feed event domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5


FEED_EVENT_ID_NAMESPACE = UUID("e71b2aec-1284-582c-a932-f86ef904d44c")


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

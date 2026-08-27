"""Feed event domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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

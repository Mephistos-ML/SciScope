"""Repository domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Repository:
    """A repository admitted into the watch graph."""

    repository_id: str
    source: str
    full_name: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubscriptionRepositoryMatch:
    """A subscription-specific relevance link to one repository."""

    subscription_id: str
    repository_id: str
    source: str
    matched_terms: tuple[str, ...] = ()
    score: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RepositoryCheckpoint:
    """Monitoring checkpoint for one watched repository."""

    subscription_id: str
    repository_id: str
    source: str
    checkpoint_key: str
    checkpoint_value: str
    updated_at: datetime

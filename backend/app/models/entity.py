"""Domain models for watched entities and subscription-scoped memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Entity:
    """A globally known thing SciScope may watch across sources.

    Examples:
    - a GitHub repository
    - a paper
    - a conference page
    - a lab website
    """

    entity_id: str
    source: str
    entity_type: str
    canonical_name: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubscriptionEntityMatch:
    """A subscription-specific relevance link to one global entity."""

    subscription_id: str
    entity_id: str
    source: str
    matched_terms: tuple[str, ...] = ()
    excluded_terms: tuple[str, ...] = ()
    score: float = 0.0
    active: bool = True
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityCheckpoint:
    """Source-specific monitoring checkpoint for one watched entity."""

    subscription_id: str
    entity_id: str
    source: str
    checkpoint_key: str
    checkpoint_value: str
    updated_at: datetime

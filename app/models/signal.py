"""Signal domain models shared across ingestion, matching, and delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RawSignal:
    """Source-scoped signal exactly as SciScope ingests it."""

    source: str
    source_type: str
    item_id: str
    title: str
    url: str
    published_at: datetime | None
    raw_text: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedSignal:
    """Signal ready for topic matching and display."""

    source: str
    item_id: str
    signal_kind: str
    title: str
    url: str
    published_at: datetime | None
    normalized_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalMatch:
    """Deterministic match result for V0 profile matching."""

    topic_slug: str
    source: str
    item_id: str
    matched: bool
    score: float
    matched_terms: tuple[str, ...] = ()
    excluded_terms: tuple[str, ...] = ()
    reason: str = ""

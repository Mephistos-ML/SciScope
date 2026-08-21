"""Models for external repository retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.signal import Signal


@dataclass(frozen=True)
class RetrievalHit:
    """One raw repository signal returned by one external retrieval lane."""

    signal: Signal


@dataclass(frozen=True)
class RetrievedCandidates:
    """One batch of retrieved repository candidates and source diagnostics."""

    candidates: tuple[Signal, ...]
    source_statuses: tuple[dict[str, object], ...]
    successful_source_count: int

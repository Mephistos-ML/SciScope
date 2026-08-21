"""Models for external repository retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.models.signal import Signal


@dataclass(frozen=True)
class RetrievalHit:
    """One raw repository signal returned by one external retrieval lane."""

    source: str
    channel: str
    query: str
    rank: int
    signal: Signal


@dataclass(frozen=True)
class CandidateProvenance:
    """Aggregated retrieval evidence for one repository candidate."""

    matched_queries: tuple[str, ...]
    matched_channels: tuple[str, ...]
    best_rank_by_channel: Mapping[str, int]
    hit_count: int


@dataclass(frozen=True)
class RepositoryCandidate:
    """One deduplicated repository candidate with retrieval provenance."""

    repository_id: str
    signal: Signal
    provenance: CandidateProvenance


@dataclass(frozen=True)
class RetrievedCandidates:
    """One batch of deduplicated repository candidates and source diagnostics."""

    candidates: tuple[RepositoryCandidate, ...]
    source_statuses: tuple[dict[str, object], ...]
    successful_source_count: int

"""Data structures for heuristic repository ranking."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.search.retrieval import RepositoryCandidate


@dataclass(frozen=True)
class RankingFeatures:
    """Source-agnostic evidence used to score one repository candidate."""

    matched_query_count: int
    total_query_count: int
    hit_count: int
    match_location_quality: float


@dataclass(frozen=True)
class RankedRepositoryCandidate:
    """One candidate with its computed relevance evidence and score."""

    candidate: RepositoryCandidate
    features: RankingFeatures
    score: float


@dataclass(frozen=True)
class RankingResult:
    """Ranked candidates and the configured output eligibility threshold."""

    ranked_candidates: tuple[RankedRepositoryCandidate, ...]
    relevance_cutoff: float

    @property
    def visible_candidates(self) -> tuple[RankedRepositoryCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.ranked_candidates
            if candidate.score >= self.relevance_cutoff
        )

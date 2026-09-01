"""Ranking orchestration for admitted repository candidates."""

from __future__ import annotations

from collections.abc import Sequence

from app.config import EXPLORE_SEARCH_RELEVANCE_CUTOFF
from app.services.search.ranking.features import build_ranking_features
from app.services.search.ranking.models import (
    RankedRepositoryCandidate,
    RankingResult,
)
from app.services.search.ranking.score import calculate_relevance_score
from app.services.search.retrieval import RepositoryCandidate


def rank_repository_candidates(
    candidates: Sequence[RepositoryCandidate],
    *,
    queries: Sequence[str],
    relevance_cutoff: float = EXPLORE_SEARCH_RELEVANCE_CUTOFF,
) -> RankingResult:
    """Rank one admitted candidate pool using source-agnostic evidence."""

    if not 0.0 <= relevance_cutoff <= 100.0:
        raise ValueError("relevance_cutoff must be between 0 and 100")

    ranked_candidates = [
        RankedRepositoryCandidate(
            candidate=candidate,
            features=features,
            score=calculate_relevance_score(features),
        )
        for candidate in candidates
        for features in (build_ranking_features(candidate, queries),)
    ]
    ranked_candidates.sort(
        key=lambda ranked: (
            -ranked.score,
            ranked.candidate.signal.title.casefold(),
        )
    )

    return RankingResult(
        ranked_candidates=tuple(ranked_candidates),
        relevance_cutoff=relevance_cutoff,
    )

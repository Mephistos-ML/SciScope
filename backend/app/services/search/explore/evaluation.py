"""Shared evaluation built from one retrieved Explore candidate pool."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.services.search.admission import AdmissionResult, run_repository_admission
from app.services.search.observability import SearchLogContext
from app.services.search.ranking import RankingResult, rank_repository_candidates
from app.services.search.retrieval import RetrievedCandidates


@dataclass(frozen=True)
class ExploreSearchEvaluation:
    """Source-agnostic admission and ranking facts for one search."""

    retrieved: RetrievedCandidates
    admission: AdmissionResult
    ranking: RankingResult


def build_explore_search_evaluation(
    retrieved: RetrievedCandidates,
    *,
    queries: Sequence[str],
    log_context: SearchLogContext | None = None,
) -> ExploreSearchEvaluation:
    """Evaluate every retrieved candidate once for all response modes."""

    admission = run_repository_admission(
        retrieved.candidates,
        log_context=log_context,
    )
    ranking = rank_repository_candidates(retrieved.candidates, queries=queries)
    return ExploreSearchEvaluation(
        retrieved=retrieved,
        admission=admission,
        ranking=ranking,
    )

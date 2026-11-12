# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Shared evaluation built from one retrieved Explore candidate pool."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from time import monotonic

from app.services.search.admission import AdmissionResult, run_repository_admission
from app.services.search.observability.context import SearchLogContext
from app.services.search.ranking import RankingResult, rank_repository_candidates
from app.services.search.ranking.models import PopularityBoostParameters
from app.services.search.retrieval import RetrievedCandidates


@dataclass(frozen=True)
class ExploreSearchEvaluation:
    """Source-agnostic admission and ranking facts for one search."""

    retrieved: RetrievedCandidates
    admission: AdmissionResult
    ranking: RankingResult
    score_threshold: float
    admission_duration_ms: int
    ranking_duration_ms: int


def build_explore_search_evaluation(
    retrieved: RetrievedCandidates,
    *,
    queries: Sequence[str],
    score_threshold: float = 0.0,
    popularity_boost: PopularityBoostParameters = PopularityBoostParameters(),
    log_context: SearchLogContext | None = None,
) -> ExploreSearchEvaluation:
    """Evaluate every retrieved candidate once for all response modes."""

    if not isfinite(score_threshold) or score_threshold < 0.0:
        raise ValueError("score_threshold must be finite and nonnegative")

    admission_started_at = monotonic()
    admission = run_repository_admission(
        retrieved.candidates,
        queries=queries,
        log_context=log_context,
    )
    admission_duration_ms = max(0, int((monotonic() - admission_started_at) * 1000))
    ranking_started_at = monotonic()
    ranking = rank_repository_candidates(
        retrieved.candidates,
        queries=queries,
        popularity_boost=popularity_boost,
    )
    ranking_duration_ms = max(0, int((monotonic() - ranking_started_at) * 1000))
    return ExploreSearchEvaluation(
        retrieved=retrieved,
        admission=admission,
        ranking=ranking,
        score_threshold=score_threshold,
        admission_duration_ms=admission_duration_ms,
        ranking_duration_ms=ranking_duration_ms,
    )

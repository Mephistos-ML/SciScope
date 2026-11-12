# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Ranking orchestration for admitted repository candidates."""

from __future__ import annotations

from collections.abc import Sequence
from math import fsum

from app.services.search.ranking.features import build_ranking_features
from app.services.search.ranking.models import (
    RankedRepositoryCandidate,
    PopularityBoostParameters,
    RankingResult,
)
from app.services.search.ranking.score import build_ranking_score_breakdown
from app.services.search.retrieval import RepositoryCandidate


def rank_repository_candidates(
    candidates: Sequence[RepositoryCandidate],
    *,
    queries: Sequence[str],
    popularity_boost: PopularityBoostParameters = PopularityBoostParameters(),
) -> RankingResult:
    """Rank one admitted candidate pool using source-agnostic evidence."""

    ranked_candidates = []
    for candidate in candidates:
        features = build_ranking_features(candidate, queries)
        breakdown = build_ranking_score_breakdown(
            features, popularity_boost=popularity_boost
        )
        ranked_candidates.append(
            RankedRepositoryCandidate(
                candidate=candidate,
                features=features,
                score=fsum(
                    [
                        *(item.contribution for item in breakdown.locations),
                        breakdown.popularity.contribution,
                    ]
                ),
                score_breakdown=breakdown,
            )
        )
    ranked_candidates.sort(
        key=lambda ranked: (
            -ranked.score,
            ranked.candidate.signal.title.casefold(),
            ranked.candidate.repository_id,
        )
    )

    return RankingResult(
        ranked_candidates=tuple(ranked_candidates),
    )

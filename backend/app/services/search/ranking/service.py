# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Ranking orchestration for admitted repository candidates."""

from __future__ import annotations

from collections.abc import Sequence
from math import fsum, isfinite

from app.services.search.ranking.features import build_ranking_features
from app.services.search.ranking.models import (
    RankedRepositoryCandidate,
    RankingResult,
)
from app.services.search.ranking.score import build_ranking_score_breakdown
from app.services.search.retrieval import RepositoryCandidate


def rank_repository_candidates(
    candidates: Sequence[RepositoryCandidate],
    *,
    queries: Sequence[str],
    score_threshold: float = 0.0,
) -> RankingResult:
    """Rank one admitted candidate pool using source-agnostic evidence."""

    if not isfinite(score_threshold) or score_threshold < 0.0:
        raise ValueError("score_threshold must be finite and nonnegative")

    ranked_candidates = []
    for candidate in candidates:
        features = build_ranking_features(candidate, queries)
        breakdown = build_ranking_score_breakdown(features)
        ranked_candidates.append(
            RankedRepositoryCandidate(
                candidate=candidate,
                features=features,
                score=fsum(item.contribution for item in breakdown.locations),
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
        score_threshold=score_threshold,
    )

# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Location-weighted logarithmic match scoring; no probability interpretation."""

from __future__ import annotations

from math import log, log1p
from types import MappingProxyType
from typing import Mapping

from app.services.search.ranking.models import (
    LocationScoreContribution,
    PopularityBoostParameters,
    PopularityScoreContribution,
    RankingFeatures,
    RankingScoreBreakdown,
)
from app.services.search.retrieval.models import RetrievalMatchLocation


# Initial policy weights, inherited from the previous heuristic. These have not
# been calibrated on held-out relevance judgments. This is their sole owner.
LOCATION_WEIGHTS: Mapping[RetrievalMatchLocation, float] = MappingProxyType(
    {
        "name": 1.00,
        "description": 0.85,
        "topic": 0.75,
        "readme": 0.65,
        "documentation": 0.55,
        "code": 0.60,
        "notebook": 0.25,
        "data": 0.25,
        "configuration": 0.25,
        "project_metadata": 0.25,
        "legal": 0.25,
        "metadata": 0.65,
        "other": 0.25,
    }
)


def build_ranking_score_breakdown(
    features: RankingFeatures,
    *,
    popularity_boost: PopularityBoostParameters = PopularityBoostParameters(),
) -> RankingScoreBreakdown:
    """Capture counts, weights and contributions for reproducible diagnostics."""

    # Clip before taking logs. Integer log handles even unusually large reported
    # counts without a float-conversion overflow; no candidate-pool normalization.
    normalized_popularity = (
        log(1 + min(features.stars, popularity_boost.reference_stars))
        / log(1 + popularity_boost.reference_stars)
        if features.stars is not None and features.stars > 0
        else 0.0
    )
    return RankingScoreBreakdown(
        locations=tuple(
            LocationScoreContribution(
                location=item.location,
                count=item.count,
                weight=LOCATION_WEIGHTS[item.location],
                contribution=LOCATION_WEIGHTS[item.location] * log1p(item.count),
            )
            for item in features.match_counts_by_location
        ),
        popularity=PopularityScoreContribution(
            stars=features.stars,
            reference_stars=popularity_boost.reference_stars,
            max_bonus=popularity_boost.max_bonus,
            normalized_popularity=normalized_popularity,
            contribution=popularity_boost.max_bonus * normalized_popularity,
        ),
    )

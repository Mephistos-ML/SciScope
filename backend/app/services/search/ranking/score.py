# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Location-weighted logarithmic match scoring; no probability interpretation."""

from __future__ import annotations

from math import log1p
from types import MappingProxyType
from typing import Mapping

from app.services.search.ranking.models import (
    LocationScoreContribution,
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
) -> RankingScoreBreakdown:
    """Capture counts, weights and contributions for reproducible diagnostics."""

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
    )

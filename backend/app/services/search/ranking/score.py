"""Score calculation for heuristic repository ranking."""

from __future__ import annotations

from app.services.search.ranking.models import RankingFeatures, RankingScoreBreakdown


def calculate_relevance_score(features: RankingFeatures) -> float:
    """Calculate a bounded 0-100 relevance score from ranking features."""

    breakdown = build_relevance_score_breakdown(features)
    return round(
        min(
            max(
                breakdown.strongest_match_points
                + breakdown.corroboration_points,
                0.0,
            ),
            100.0,
        ),
        2,
    )


def build_relevance_score_breakdown(
    features: RankingFeatures,
) -> RankingScoreBreakdown:
    """Build score contributions from one repository's ranking features."""

    return RankingScoreBreakdown(
        strongest_match_quality=features.strongest_match_quality,
        strongest_match_points=round(85.0 * features.strongest_match_quality, 2),
        corroboration_quality=features.corroboration_quality,
        corroboration_points=round(15.0 * features.corroboration_quality, 2),
    )

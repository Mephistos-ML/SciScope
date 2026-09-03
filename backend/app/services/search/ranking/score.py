"""Score calculation for heuristic repository ranking."""

from __future__ import annotations

from math import log1p

from app.services.search.ranking.models import RankingFeatures, RankingScoreBreakdown


def calculate_relevance_score(features: RankingFeatures) -> float:
    """Calculate a bounded 0-100 relevance score from ranking features."""

    breakdown = build_relevance_score_breakdown(features)
    return round(
        min(
            max(
                breakdown.query_coverage_points
                + breakdown.match_location_points
                + breakdown.evidence_density_points,
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

    query_coverage = _query_coverage(features)
    evidence_density = _evidence_density(features.evidence_count)
    return RankingScoreBreakdown(
        query_coverage=query_coverage,
        query_coverage_points=round(40.0 * query_coverage, 2),
        match_location_quality=features.match_location_quality,
        match_location_points=round(45.0 * features.match_location_quality, 2),
        evidence_density=evidence_density,
        evidence_density_points=round(15.0 * evidence_density, 2),
    )


def _query_coverage(features: RankingFeatures) -> float:
    if features.total_query_count <= 0 or features.matched_query_count <= 0:
        return 0.0

    coverage = features.query_coverage_alignment
    if coverage <= 0.0:
        coverage = float(features.matched_query_count)
    return log1p(min(coverage, features.total_query_count)) / log1p(
        features.total_query_count
    )


def _evidence_density(evidence_count: int) -> float:
    if evidence_count <= 0:
        return 0.0
    return min(1.0, log1p(evidence_count) / log1p(5))

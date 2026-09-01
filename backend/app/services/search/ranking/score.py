"""Score calculation for heuristic repository ranking."""

from __future__ import annotations

from math import log1p

from app.services.search.ranking.models import RankingFeatures


def calculate_relevance_score(features: RankingFeatures) -> float:
    """Calculate a bounded 0-100 relevance score from ranking features."""

    query_coverage = _query_coverage(features)
    evidence_density = _evidence_density(features.hit_count)
    score = (
        40.0 * query_coverage
        + 45.0 * features.match_location_quality
        + 15.0 * evidence_density
    )
    return round(min(max(score, 0.0), 100.0), 2)


def _query_coverage(features: RankingFeatures) -> float:
    if features.total_query_count <= 0 or features.matched_query_count <= 0:
        return 0.0

    bounded_match_count = min(
        features.matched_query_count,
        features.total_query_count,
    )
    return log1p(bounded_match_count) / log1p(features.total_query_count)


def _evidence_density(hit_count: int) -> float:
    if hit_count <= 0:
        return 0.0
    return min(1.0, log1p(hit_count) / log1p(5))

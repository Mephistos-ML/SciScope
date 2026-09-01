"""Feature extraction for source-agnostic repository ranking."""

from __future__ import annotations

from collections.abc import Sequence

from app.services.search.ranking.models import RankingFeatures
from app.services.search.retrieval import RepositoryCandidate, RetrievalMatchEvidence


_MATCH_LOCATION_WEIGHTS = {
    "name": 1.00,
    "description": 0.85,
    "topic": 0.75,
    "readme": 0.65,
    "documentation": 0.55,
    "code": 0.40,
    "other": 0.25,
    "metadata": 0.65,
}


def build_ranking_features(
    candidate: RepositoryCandidate,
    queries: Sequence[str],
) -> RankingFeatures:
    """Build ranking features without relying on source or retrieval channel."""

    normalized_queries = tuple(
        query.strip() for query in queries if query.strip()
    )
    evidence = candidate.provenance.match_evidence

    return RankingFeatures(
        matched_query_count=len(candidate.provenance.matched_queries),
        total_query_count=len(normalized_queries),
        hit_count=candidate.provenance.hit_count,
        evidence_count=len(evidence),
        match_location_quality=_build_match_location_quality(
            evidence,
            normalized_queries,
        ),
    )


def _build_match_location_quality(
    evidence: Sequence[RetrievalMatchEvidence],
    queries: Sequence[str],
) -> float:
    if not queries:
        return 0.0

    best_weight_by_query: dict[str, float] = {}
    for item in evidence:
        normalized_query = item.query.strip()
        if not normalized_query:
            continue
        weight = _MATCH_LOCATION_WEIGHTS[item.location]
        best_weight_by_query[normalized_query] = max(
            best_weight_by_query.get(normalized_query, 0.0),
            weight,
        )

    matched_weights = [
        best_weight_by_query.get(query, 0.0)
        for query in queries
        if query in best_weight_by_query
    ]
    if not matched_weights:
        return 0.0
    return sum(matched_weights) / len(matched_weights)

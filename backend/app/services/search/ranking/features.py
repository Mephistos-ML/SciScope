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
    "code": 0.60,
    "other": 0.25,
    "metadata": 0.65,
}


def build_ranking_features(
    candidate: RepositoryCandidate,
    queries: Sequence[str],
) -> RankingFeatures:
    """Build ranking features without relying on source or retrieval channel."""

    normalized_queries = tuple(
        _normalize_query(query) for query in queries if query.strip()
    )
    evidence = candidate.provenance.match_evidence
    evidence_quality_by_query = _build_evidence_quality_by_query(
        evidence,
        normalized_queries,
    )
    ordered_evidence_quality = tuple(
        evidence_quality_by_query.get(query, 0.0)
        for query in normalized_queries
    )
    strongest_match_quality = max(ordered_evidence_quality, default=0.0)

    return RankingFeatures(
        matched_query_count=len(candidate.provenance.matched_queries),
        total_query_count=len(normalized_queries),
        hit_count=candidate.provenance.hit_count,
        evidence_count=len(evidence),
        strongest_match_quality=strongest_match_quality,
        corroboration_quality=_build_corroboration_quality(
            ordered_evidence_quality,
            strongest_match_quality=strongest_match_quality,
        ),
    )


def _build_evidence_quality_by_query(
    evidence: Sequence[RetrievalMatchEvidence],
    queries: Sequence[str],
) -> dict[str, float]:
    query_priority_by_value = {
        query: _query_priority_weight(index)
        for index, query in enumerate(queries)
    }
    best_quality_by_query: dict[str, float] = {}
    for item in evidence:
        normalized_query = _normalize_query(item.query)
        priority = query_priority_by_value.get(normalized_query)
        if priority is None:
            continue
        quality = _MATCH_LOCATION_WEIGHTS[item.location] * item.alignment * priority
        best_quality_by_query[normalized_query] = max(
            best_quality_by_query.get(normalized_query, 0.0),
            quality,
        )
    return best_quality_by_query


def _build_corroboration_quality(
    evidence_quality_by_query: Sequence[float],
    *,
    strongest_match_quality: float,
) -> float:
    """Reward independent supporting queries without letting them dominate one strong match."""

    if strongest_match_quality <= 0.0:
        return 0.0

    support = sorted(evidence_quality_by_query, reverse=True)[1:]
    remaining_uncertainty = 1.0
    for quality in support:
        normalized_support = min(quality / strongest_match_quality, 1.0)
        remaining_uncertainty *= 1.0 - normalized_support
    return 1.0 - remaining_uncertainty


def _query_priority_weight(index: int) -> float:
    """Prefer the primary interpretation slightly without hiding stronger fallback evidence."""

    return max(0.8, 1.0 - index * 0.05)


def _normalize_query(query: str) -> str:
    """Make query identity stable across provider and catalog retrieval."""

    return " ".join(query.casefold().split())

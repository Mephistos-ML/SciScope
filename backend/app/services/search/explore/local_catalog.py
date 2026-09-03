"""Quality-based policy for deciding whether local catalog retrieval is sufficient."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from app import config
from app.services.search.explore.canonical import select_canonical_candidates
from app.services.search.explore.evaluation import ExploreSearchEvaluation


@dataclass(frozen=True)
class LocalCatalogSufficiency:
    """Source-agnostic evidence that a local result pool can stand alone."""

    strong_candidate_count: int
    covered_query_count: int
    required_covered_query_count: int
    query_coverage: float
    sufficient: bool


def assess_local_catalog_sufficiency(
    evaluation: ExploreSearchEvaluation,
    *,
    queries: tuple[str, ...],
    min_strong_results: int = config.EXPLORE_LOCAL_MIN_STRONG_RESULTS,
    required_query_coverage: float = config.EXPLORE_LOCAL_REQUIRED_QUERY_COVERAGE,
    min_query_alignment: float = config.EXPLORE_LOCAL_MIN_QUERY_ALIGNMENT,
) -> LocalCatalogSufficiency:
    """Require both a strong result pool and broad current-query coverage."""

    normalized_queries = tuple(
        dict.fromkeys(_normalize(query) for query in queries if _normalize(query))
    )
    strong_candidates = select_canonical_candidates(evaluation)
    alignment_by_query = {query: 0.0 for query in normalized_queries}
    for ranked in strong_candidates:
        for evidence in ranked.candidate.provenance.match_evidence:
            query = _normalize(evidence.query)
            if query in alignment_by_query:
                alignment_by_query[query] = max(
                    alignment_by_query[query],
                    min(1.0, max(0.0, evidence.alignment)),
                )

    required_covered_query_count = ceil(
        len(normalized_queries) * required_query_coverage
    )
    covered_query_count = sum(
        alignment >= min_query_alignment
        for alignment in alignment_by_query.values()
    )
    query_coverage = (
        covered_query_count / len(normalized_queries) if normalized_queries else 0.0
    )
    return LocalCatalogSufficiency(
        strong_candidate_count=len(strong_candidates),
        covered_query_count=covered_query_count,
        required_covered_query_count=required_covered_query_count,
        query_coverage=query_coverage,
        sufficient=(
            len(strong_candidates) >= min_strong_results
            and covered_query_count >= required_covered_query_count
        ),
    )


def _normalize(query: str) -> str:
    return " ".join(query.casefold().split())

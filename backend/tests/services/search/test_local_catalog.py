"""Tests for quality-based local catalog fallback policy."""

from __future__ import annotations

from app.models.signal import Signal
from app.services.search.admission import run_repository_admission
from app.services.search.explore.evaluation import ExploreSearchEvaluation
from app.services.search.explore.local_catalog import assess_local_catalog_sufficiency
from app.services.search.ranking import rank_repository_candidates
from app.services.search.retrieval import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievedCandidates,
    RetrievalMatchEvidence,
)


def test_local_catalog_requires_broad_query_coverage_not_just_candidate_count() -> None:
    queries = ("query a", "query b", "query c", "query d", "query e")
    evaluation = _build_evaluation(("query a", "query b", "query c"))

    result = assess_local_catalog_sufficiency(
        evaluation,
        queries=queries,
        min_strong_results=1,
        required_query_coverage=0.8,
        min_query_alignment=0.8,
    )

    assert result.strong_candidate_count == 3
    assert result.covered_query_count == 3
    assert result.required_covered_query_count == 4
    assert result.sufficient is False


def test_local_catalog_accepts_aligned_semantic_coverage() -> None:
    queries = ("query a", "query b", "query c", "query d", "query e")
    evaluation = _build_evaluation(
        ("query a", "query b", "query c", "query d"),
        alignment=0.82,
    )

    result = assess_local_catalog_sufficiency(
        evaluation,
        queries=queries,
        min_strong_results=1,
        required_query_coverage=0.8,
        min_query_alignment=0.8,
    )

    assert result.query_coverage == 0.8
    assert result.sufficient is True


def _build_evaluation(
    matched_queries: tuple[str, ...],
    *,
    alignment: float = 1.0,
) -> ExploreSearchEvaluation:
    candidates = tuple(
        RepositoryCandidate(
            repository_id=f"github:repo:{index}",
            signal=Signal(
                source="github",
                kind="repository",
                item_id=f"github:repo:{index}",
                title=f"org/tool-{index}",
                url=f"https://github.com/org/tool-{index}",
                published_at=None,
                raw_text="Scientific software toolkit.",
                payload={"repo": f"org/tool-{index}", "language": "Python"},
            ),
            provenance=CandidateProvenance(
                matched_queries=(query,),
                matched_channels=("semantic_catalog",),
                best_rank_by_channel={"semantic_catalog": 1},
                hit_count=1,
                match_evidence=(
                    RetrievalMatchEvidence(
                        query=query,
                        location="description",
                        alignment=alignment,
                    ),
                ),
                origins=("catalog",),
            ),
        )
        for index, query in enumerate(matched_queries)
    )
    retrieved = RetrievedCandidates(
        candidates=candidates,
        source_statuses=(),
        successful_source_count=1,
    )
    return ExploreSearchEvaluation(
        retrieved=retrieved,
        admission=run_repository_admission(candidates, mode="off"),
        ranking=rank_repository_candidates(candidates, queries=matched_queries, relevance_cutoff=0),
    )

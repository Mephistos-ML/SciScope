"""Tests for durable Explore execution snapshots."""

from __future__ import annotations

from app.models.ai import AiSearchPlan
from app.models.signal import Signal
from app.services.search.explore.execution import (
    ExploreSearchExecution,
    deserialize_execution,
    serialize_execution,
)
from app.services.search.retrieval import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievedCandidates,
    RetrievalMatchEvidence,
)


def test_execution_snapshot_round_trips_per_evidence_provenance() -> None:
    candidate = RepositoryCandidate(
        repository_id="github:repo:science/example",
        signal=Signal(
            source="github",
            kind="repository",
            item_id="github:repo:science/example",
            title="science/example",
            url="https://github.com/science/example",
            published_at=None,
            raw_text="example",
        ),
        provenance=CandidateProvenance(
            matched_queries=("example query",),
            matched_channels=("code_search",),
            best_rank_by_channel={"code_search": 3},
            hit_count=1,
            match_evidence=(
                RetrievalMatchEvidence(
                    query="example query",
                    location="code",
                    path="src/example.py",
                    channel="code_search",
                    origin="provider",
                    retrieval_rank=3,
                ),
            ),
        ),
    )
    execution = ExploreSearchExecution(
        ai_search_plan=AiSearchPlan(status="ready", queries=("example query",)),
        executed_queries=("example query",),
        retrieved=RetrievedCandidates(
            candidates=(candidate,),
            source_statuses=(),
            successful_source_count=1,
        ),
    )

    restored = deserialize_execution(serialize_execution(execution))

    evidence = restored.retrieved.candidates[0].provenance.match_evidence[0]
    assert evidence.channel == "code_search"
    assert evidence.origin == "provider"
    assert evidence.retrieval_rank == 3

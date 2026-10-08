"""Regression tests for retaining candidates across timeout fallback queries."""

from __future__ import annotations

import pytest

from app.models.signal import Signal
from app.services.search.explore import service
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievedCandidates,
    RetrievalLaneOutcome,
)


def _candidate(name: str, query: str) -> RepositoryCandidate:
    repository_id = f"github:repo:science/{name}"
    return RepositoryCandidate(
        repository_id=repository_id,
        signal=Signal(
            source="github", kind="repository", item_id=repository_id,
            title=f"science/{name}", url=f"https://github.com/science/{name}",
            published_at=None, raw_text=name,
        ),
        provenance=CandidateProvenance(
            matched_queries=(query,), matched_channels=("repository_search",),
            best_rank_by_channel={"repository_search": 1}, hit_count=1,
        ),
    )


@pytest.mark.parametrize("next_result", ["success", "empty", "timeout"])
def test_timeout_fallback_retains_results_and_diagnostics(monkeypatch, next_result):
    calls = []
    monkeypatch.setattr(service, "retrieve_catalog_candidates", lambda *args, **kwargs: ())

    def retrieve(queries, **kwargs):
        query = queries[0]
        calls.append(query)
        timed_out = query == "first" or next_result == "timeout"
        if query == "first":
            candidates = (_candidate("retained", query),)
        elif next_result == "empty":
            candidates = ()
        elif next_result == "success":
            candidates = (_candidate("retained", query), _candidate("additional", query))
        else:
            candidates = (_candidate("additional", query),)
        return RetrievedCandidates(
            candidates=candidates,
            source_statuses=({"source": "gitlab", "status": "timed_out" if timed_out else "ok"},),
            successful_source_count=1,
            partial=timed_out,
            warnings=(f"{query} timed out" if timed_out else "second diagnostic",),
            lane_outcomes=(RetrievalLaneOutcome(
                source="gitlab", channel="repository_search",
                status="timed_out" if timed_out else "completed",
                candidate_count=len(candidates), duration_ms=1,
            ),),
        )

    monkeypatch.setattr(service, "_run_external_retrieval", retrieve)
    queries = ("first", "second") if next_result == "timeout" else ("first", "second", "unused")
    sequence = service._retrieve_planned_queries(
        lanes=(),
        queries=queries, topic_description="Scientific tools",
        ai_search_plan_payload={"status": "ready", "queries": list(queries)},
        progress_callback=None, log_context=None, database_url="unused",
    )

    retries = service.MAX_TIMEOUT_ATTEMPTS_PER_QUERY
    second_attempts = retries if next_result == "timeout" else 1
    assert calls == ["first"] * retries + ["second"] * second_attempts
    assert sequence.executed_queries == ("first", "second")
    candidates = {candidate.repository_id: candidate for candidate in sequence.retrieved.candidates}
    expected_ids = {"github:repo:science/retained"}
    if next_result != "empty":
        expected_ids.add("github:repo:science/additional")
    assert set(candidates) == expected_ids
    assert candidates["github:repo:science/retained"].provenance.matched_queries == (
        ("first", "second") if next_result == "success" else ("first",)
    )
    assert sequence.retrieved.partial is True
    assert sequence.retrieved.warnings == (
        "first timed out", "second timed out" if next_result == "timeout" else "second diagnostic",
    )
    assert len(sequence.retrieved.source_statuses) == retries + second_attempts
    assert sequence.retrieved.source_statuses[0]["status"] == "timed_out"
    assert sequence.retrieved.successful_source_count == retries + second_attempts
    assert [(outcome.query, outcome.attempt) for outcome in sequence.retrieved.lane_outcomes] == (
        [("first", number) for number in range(1, retries + 1)] +
        [("second", number) for number in range(1, second_attempts + 1)]
    )
    assert [attempt.status for attempt in sequence.attempts] == (
        ["timed_out"] * retries + ["timed_out" if next_result == "timeout" else "completed"] * second_attempts
    )

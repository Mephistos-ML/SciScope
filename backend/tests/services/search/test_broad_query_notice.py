"""Broad-search guidance does not disclose provider limits or alter partial status."""

import pytest

from app.integrations.repositories.common.models import RepositoryDiscoveryBatch
from app.services.search.retrieval.discovery import discover_candidates_across_sources
from app.services.search.retrieval.models import RetrievalLane
from app.services.search.retrieval.models import RetrievedCandidates
from app.services.search.explore.evaluation import build_explore_search_evaluation
from app.services.search.explore.response import build_explore_search_payload


@pytest.mark.parametrize("total, expected", [(1000, False), (1001, True)])
def test_broad_query_guidance_even_when_no_files_are_returned(total, expected):
    def discover(queries, *, deadline_monotonic):
        return RepositoryDiscoveryBatch((), (total,))

    result = discover_candidates_across_sources(
        ["one", "two"], lanes=[RetrievalLane("github", "code_search", discover)],
    )
    assert result["partial"] is False
    warnings = result["warnings"]
    assert len(warnings) == int(expected)
    if expected:
        assert warnings[0] == "Try a more specific search: add a method, tool, or scientific task."
        assert not any(term in warnings[0] for term in ("1000", "GitHub", "files", "API"))
    evaluation = build_explore_search_evaluation(
        RetrievedCandidates(
            candidates=(), source_statuses=(), successful_source_count=1,
            warnings=tuple(warnings),
        ), queries=["one"],
    )
    payload = build_explore_search_payload(
        topic_description="science", ai_search_plan_payload={"status": "ready"},
        evaluation=evaluation,
    )
    assert payload["message"] == (warnings[0] if expected else None)
    assert payload["partial"] is False

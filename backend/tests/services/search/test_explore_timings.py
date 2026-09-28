"""Tests for Explore beta timing facts."""

from __future__ import annotations

import pytest

from app.services.search.explore.timings import ExploreSearchTimings


def test_explore_search_timings_serialize_for_beta() -> None:
    timings = ExploreSearchTimings(
        ai_planning_duration_ms=1800,
        retrieval_duration_ms=12400,
        evaluation_duration_ms=200,
        response_build_duration_ms=35,
        total_duration_ms=14435,
    )

    assert timings.to_beta_payload() == {
        "aiPlanningDurationMs": 1800,
        "retrievalDurationMs": 12400,
        "evaluationDurationMs": 200,
        "responseBuildDurationMs": 35,
        "totalDurationMs": 14435,
    }


def test_explore_search_timings_reject_negative_durations() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        ExploreSearchTimings(
            ai_planning_duration_ms=-1,
            retrieval_duration_ms=0,
            evaluation_duration_ms=0,
            response_build_duration_ms=0,
            total_duration_ms=0,
        )

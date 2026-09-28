"""Timing facts for one completed Explore search."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExploreSearchTimings:
    """Durations captured by Explore orchestration in milliseconds."""

    ai_planning_duration_ms: int
    retrieval_duration_ms: int
    evaluation_duration_ms: int
    response_build_duration_ms: int
    total_duration_ms: int

    def __post_init__(self) -> None:
        for value in (
            self.ai_planning_duration_ms,
            self.retrieval_duration_ms,
            self.evaluation_duration_ms,
            self.response_build_duration_ms,
            self.total_duration_ms,
        ):
            if value < 0:
                raise ValueError("Explore search timings must not be negative.")

    def to_beta_payload(self) -> dict[str, int]:
        """Serialize timing facts for the restricted beta response."""

        return {
            "aiPlanningDurationMs": self.ai_planning_duration_ms,
            "retrievalDurationMs": self.retrieval_duration_ms,
            "evaluationDurationMs": self.evaluation_duration_ms,
            "responseBuildDurationMs": self.response_build_duration_ms,
            "totalDurationMs": self.total_duration_ms,
        }

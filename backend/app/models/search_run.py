"""Durable execution facts for one Explore search run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


SearchRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "completed_partial",
    "failed",
    "interrupted",
]
SearchOperationKind = Literal["initial", "expansion"]
SearchOperationStatus = Literal[
    "queued",
    "running",
    "completed",
    "completed_partial",
    "failed",
    "interrupted",
]


@dataclass(frozen=True)
class SearchRun:
    """One logical Explore search, including all incremental expansions."""

    run_id: str
    owner_user_id: str | None
    topic_description: str
    topic_hash: str
    status: SearchRunStatus
    planner_mode: str
    planner_model: str | None
    ranking_policy_version: str
    backend_revision: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    partial: bool = False
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class SearchRunOperation:
    """One asynchronous execution for a SearchRun."""

    operation_id: str
    run_id: str
    kind: SearchOperationKind
    status: SearchOperationStatus
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lease_holder_id: str | None = None
    lease_expires_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class SearchRunStage:
    """One completed or in-progress stage within a SearchRun operation."""

    run_id: str
    operation_id: str
    stage_number: int
    status: str
    executed_query_ids: tuple[str, ...]
    retrieved_candidate_count: int
    admitted_candidate_count: int
    visible_candidate_count: int
    timings: dict[str, int]
    started_at: datetime
    completed_at: datetime | None = None


@dataclass(frozen=True)
class SearchRunProviderOutcome:
    """One provider/channel outcome observed during a SearchRun stage."""

    outcome_id: str
    run_id: str
    operation_id: str
    stage_number: int
    source: str
    channel: str
    query_id: str
    attempt: int
    status: str
    candidate_count: int
    duration_ms: int
    retry_after_seconds: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    details: dict[str, Any] | None = None

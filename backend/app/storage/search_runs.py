"""Persistence for durable Explore search run execution facts."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.database.records.search_runs import (
    SearchRunOperationRecordModel,
    SearchRunProviderOutcomeRecordModel,
    SearchRunRecordModel,
    SearchRunStageRecordModel,
)
from app.database.session import session_scope
from app.models.search_run import (
    SearchRun,
    SearchRunOperation,
    SearchRunProviderOutcome,
    SearchRunStage,
)


def create_search_run(run: SearchRun, *, database_url: str) -> None:
    """Persist a newly created logical Explore search run."""

    with session_scope(database_url) as session:
        session.add(
            SearchRunRecordModel(
                run_id=run.run_id,
                owner_user_id=run.owner_user_id,
                topic_description=run.topic_description,
                topic_hash=run.topic_hash,
                response_mode=run.response_mode,
                status=run.status,
                planner_mode=run.planner_mode,
                planner_model=run.planner_model,
                ranking_policy_version=run.ranking_policy_version,
                backend_revision=run.backend_revision,
                created_at=run.created_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
                partial=run.partial,
                error_code=run.error_code,
                error_message=run.error_message,
                response_payload_json=run.response_payload,
                execution_state_json=run.execution_state,
            )
        )


def create_search_run_operation(
    operation: SearchRunOperation,
    *,
    database_url: str,
) -> None:
    """Persist one initial-search or expansion operation."""

    with session_scope(database_url) as session:
        session.add(
            SearchRunOperationRecordModel(
                operation_id=operation.operation_id,
                run_id=operation.run_id,
                kind=operation.kind,
                status=operation.status,
                queued_at=operation.queued_at,
                started_at=operation.started_at,
                completed_at=operation.completed_at,
                lease_holder_id=operation.lease_holder_id,
                lease_expires_at=operation.lease_expires_at,
                error_code=operation.error_code,
                error_message=operation.error_message,
            )
        )


def record_search_run_stage(stage: SearchRunStage, *, database_url: str) -> None:
    """Persist one stage report for a durable Explore search run."""

    with session_scope(database_url) as session:
        session.add(
            SearchRunStageRecordModel(
                run_id=stage.run_id,
                stage_number=stage.stage_number,
                operation_id=stage.operation_id,
                status=stage.status,
                executed_query_ids_json=list(stage.executed_query_ids),
                retrieved_candidate_count=stage.retrieved_candidate_count,
                admitted_candidate_count=stage.admitted_candidate_count,
                visible_candidate_count=stage.visible_candidate_count,
                timings_json=dict(stage.timings),
                started_at=stage.started_at,
                completed_at=stage.completed_at,
            )
        )


def record_search_run_provider_outcomes(
    outcomes: Sequence[SearchRunProviderOutcome],
    *,
    database_url: str,
) -> None:
    """Persist provider/channel facts observed during one search stage."""

    if not outcomes:
        return

    with session_scope(database_url) as session:
        session.add_all(
            SearchRunProviderOutcomeRecordModel(
                outcome_id=outcome.outcome_id,
                run_id=outcome.run_id,
                operation_id=outcome.operation_id,
                stage_number=outcome.stage_number,
                source=outcome.source,
                channel=outcome.channel,
                query_id=outcome.query_id,
                attempt=outcome.attempt,
                status=outcome.status,
                candidate_count=outcome.candidate_count,
                duration_ms=outcome.duration_ms,
                retry_after_seconds=outcome.retry_after_seconds,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
                details_json=outcome.details,
            )
            for outcome in outcomes
        )


def count_search_run_stages(run_id: str, *, database_url: str) -> int:
    """Return the number of completed run stages persisted so far."""

    with session_scope(database_url) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(SearchRunStageRecordModel)
                .where(SearchRunStageRecordModel.run_id == run_id)
            )
            or 0
        )


def count_search_run_provider_outcomes(run_id: str, *, database_url: str) -> int:
    """Return the number of durable provider outcomes for one run."""

    with session_scope(database_url) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(SearchRunProviderOutcomeRecordModel)
                .where(SearchRunProviderOutcomeRecordModel.run_id == run_id)
            )
            or 0
        )


def get_search_run(run_id: str, *, database_url: str) -> SearchRun | None:
    """Return the durable top-level record for one Explore search run."""

    with session_scope(database_url) as session:
        record = session.get(SearchRunRecordModel, run_id)
        if record is None:
            return None
        return SearchRun(
            run_id=record.run_id,
            owner_user_id=record.owner_user_id,
            topic_description=record.topic_description,
            topic_hash=record.topic_hash,
            response_mode=record.response_mode,
            status=record.status,  # type: ignore[arg-type]
            planner_mode=record.planner_mode,
            planner_model=record.planner_model,
            ranking_policy_version=record.ranking_policy_version,
            backend_revision=record.backend_revision,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            partial=record.partial,
            error_code=record.error_code,
            error_message=record.error_message,
            response_payload=record.response_payload_json,
            execution_state=record.execution_state_json,
        )


def update_search_run(
    run_id: str,
    *,
    status: str,
    partial: bool = False,
    error_code: str | None = None,
    error_message: str | None = None,
    response_payload: dict[str, Any] | None = None,
    execution_state: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    database_url: str,
) -> None:
    """Update the durable state of one Explore search run."""

    with session_scope(database_url) as session:
        record = session.get(SearchRunRecordModel, run_id)
        if record is None:
            return
        record.status = status
        record.partial = partial
        record.error_code = error_code
        record.error_message = error_message
        if response_payload is not None:
            record.response_payload_json = response_payload
        if execution_state is not None:
            record.execution_state_json = execution_state
        if started_at is not None:
            record.started_at = started_at
        if completed_at is not None:
            record.completed_at = completed_at


def update_search_run_operation(
    operation_id: str,
    *,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    database_url: str,
) -> None:
    """Update the durable lifecycle state of one background operation."""

    with session_scope(database_url) as session:
        record = session.get(SearchRunOperationRecordModel, operation_id)
        if record is None:
            return
        record.status = status
        record.error_code = error_code
        record.error_message = error_message
        if started_at is not None:
            record.started_at = started_at
        if completed_at is not None:
            record.completed_at = completed_at

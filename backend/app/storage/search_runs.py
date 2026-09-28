"""Persistence for durable Explore search run execution facts."""

from __future__ import annotations

from collections.abc import Sequence

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
        )

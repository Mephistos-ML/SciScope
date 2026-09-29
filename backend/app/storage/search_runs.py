"""Persistence for durable Explore search run execution facts."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update

from app.database.records.search_runs import (
    SearchRunOperationRecordModel,
    SearchRunProviderOutcomeRecordModel,
    SearchRunRankingCandidateRecordModel,
    SearchRunRankingLabelRecordModel,
    SearchRunRecordModel,
    SearchRunStageRecordModel,
)
from app.database.session import session_scope
from app.models.search_run import (
    SearchRun,
    SearchRunOperation,
    SearchRunProviderOutcome,
    SearchRankingCandidateReport,
    SearchRunRankingLabel,
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


def claim_next_search_run_operation(
    *,
    holder_id: str,
    now: datetime,
    lease_expires_at: datetime,
    database_url: str,
) -> SearchRunOperation | None:
    """Atomically lease the oldest queued or abandoned search operation."""

    claimable = or_(
        SearchRunOperationRecordModel.status == "queued",
        and_(
            SearchRunOperationRecordModel.status == "running",
            or_(
                SearchRunOperationRecordModel.lease_expires_at.is_(None),
                SearchRunOperationRecordModel.lease_expires_at < now,
            ),
        ),
    )
    with session_scope(database_url) as session:
        operation_id = session.scalar(
            select(SearchRunOperationRecordModel.operation_id)
            .where(claimable)
            .order_by(SearchRunOperationRecordModel.queued_at)
            .limit(1)
        )
        if operation_id is None:
            return None
        claimed = session.execute(
            update(SearchRunOperationRecordModel)
            .where(
                SearchRunOperationRecordModel.operation_id == operation_id,
                claimable,
            )
            .values(
                status="running",
                started_at=func.coalesce(SearchRunOperationRecordModel.started_at, now),
                lease_holder_id=holder_id,
                lease_expires_at=lease_expires_at,
            )
        )
        if claimed.rowcount != 1:
            return None
        record = session.get(SearchRunOperationRecordModel, operation_id)
        return _to_search_run_operation(record) if record is not None else None


def renew_search_run_operation_lease(
    operation_id: str,
    *,
    holder_id: str,
    lease_expires_at: datetime,
    database_url: str,
) -> bool:
    """Extend a lease only while it remains owned by this worker."""

    with session_scope(database_url) as session:
        renewed = session.execute(
            update(SearchRunOperationRecordModel)
            .where(
                SearchRunOperationRecordModel.operation_id == operation_id,
                SearchRunOperationRecordModel.status == "running",
                SearchRunOperationRecordModel.lease_holder_id == holder_id,
            )
            .values(lease_expires_at=lease_expires_at)
        )
        return renewed.rowcount == 1


def release_search_run_operation_lease(
    operation_id: str,
    *,
    holder_id: str,
    database_url: str,
) -> None:
    """Remove a finished worker's lease without touching another worker's claim."""

    with session_scope(database_url) as session:
        session.execute(
            update(SearchRunOperationRecordModel)
            .where(
                SearchRunOperationRecordModel.operation_id == operation_id,
                SearchRunOperationRecordModel.lease_holder_id == holder_id,
            )
            .values(lease_holder_id=None, lease_expires_at=None)
        )


def record_search_run_stage(stage: SearchRunStage, *, database_url: str) -> None:
    """Persist one stage report for a durable Explore search run."""

    with session_scope(database_url) as session:
        record = session.get(SearchRunStageRecordModel, (stage.run_id, stage.stage_number))
        if record is None:
            record = SearchRunStageRecordModel(
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
            session.add(record)
            return
        record.operation_id = stage.operation_id
        record.status = stage.status
        record.executed_query_ids_json = list(stage.executed_query_ids)
        record.retrieved_candidate_count = stage.retrieved_candidate_count
        record.admitted_candidate_count = stage.admitted_candidate_count
        record.visible_candidate_count = stage.visible_candidate_count
        record.timings_json = dict(stage.timings)
        record.started_at = stage.started_at
        record.completed_at = stage.completed_at


def record_search_run_provider_outcomes(
    outcomes: Sequence[SearchRunProviderOutcome],
    *,
    database_url: str,
) -> None:
    """Persist provider/channel facts observed during one search stage."""

    if not outcomes:
        return

    with session_scope(database_url) as session:
        stage_keys = {(outcome.run_id, outcome.stage_number) for outcome in outcomes}
        for run_id, stage_number in stage_keys:
            session.execute(
                delete(SearchRunProviderOutcomeRecordModel).where(
                    SearchRunProviderOutcomeRecordModel.run_id == run_id,
                    SearchRunProviderOutcomeRecordModel.stage_number == stage_number,
                )
            )
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


def record_search_run_ranking_candidates(
    run_id: str,
    stage_number: int,
    candidates: Sequence[SearchRankingCandidateReport],
    *,
    database_url: str,
) -> None:
    """Persist immutable candidate-level inputs for offline reranking."""

    if not candidates:
        return
    with session_scope(database_url) as session:
        session.execute(
            delete(SearchRunRankingCandidateRecordModel).where(
                SearchRunRankingCandidateRecordModel.run_id == run_id,
                SearchRunRankingCandidateRecordModel.stage_number == stage_number,
            )
        )
        session.add_all(
            SearchRunRankingCandidateRecordModel(
                run_id=run_id,
                stage_number=stage_number,
                repository_id=candidate.repository_id,
                repository_source=candidate.repository_source,
                rank_position=candidate.rank_position,
                final_score=candidate.final_score,
                candidate_facts_json=candidate.candidate_facts,
                retrieval_facts_json=candidate.retrieval_facts,
                admission_facts_json=candidate.admission_facts,
                ranking_features_json=candidate.ranking_features,
                score_breakdown_json=candidate.score_breakdown,
            )
            for candidate in candidates
        )


def list_search_run_ranking_repository_ids(
    run_id: str,
    stage_number: int,
    *,
    database_url: str,
) -> set[str]:
    """Return candidate identities available for one immutable snapshot."""

    with session_scope(database_url) as session:
        return set(
            session.scalars(
                select(SearchRunRankingCandidateRecordModel.repository_id).where(
                    SearchRunRankingCandidateRecordModel.run_id == run_id,
                    SearchRunRankingCandidateRecordModel.stage_number == stage_number,
                )
            )
        )


def upsert_search_run_ranking_labels(
    labels: Sequence[SearchRunRankingLabel],
    *,
    database_url: str,
) -> None:
    """Store human labels without changing the referenced snapshot facts."""

    with session_scope(database_url) as session:
        for label in labels:
            record = session.get(
                SearchRunRankingLabelRecordModel,
                (label.run_id, label.repository_id, label.user_id),
            )
            if record is None:
                session.add(
                    SearchRunRankingLabelRecordModel(
                        run_id=label.run_id,
                        repository_id=label.repository_id,
                        user_id=label.user_id,
                        stage_number=label.stage_number,
                        label=label.label,
                        created_at=label.created_at,
                        updated_at=label.updated_at,
                    )
                )
                continue
            record.stage_number = label.stage_number
            record.label = label.label
            record.updated_at = label.updated_at


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


def count_search_run_ranking_candidates(run_id: str, *, database_url: str) -> int:
    """Return the number of immutable ranking candidates for one run."""

    with session_scope(database_url) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(SearchRunRankingCandidateRecordModel)
                .where(SearchRunRankingCandidateRecordModel.run_id == run_id)
            )
            or 0
        )


def get_search_run_stage(
    run_id: str,
    stage_number: int,
    *,
    database_url: str,
) -> SearchRunStage | None:
    """Return one durable stage report for internal diagnostics."""

    with session_scope(database_url) as session:
        record = session.get(SearchRunStageRecordModel, (run_id, stage_number))
        if record is None:
            return None
        return SearchRunStage(
            run_id=record.run_id,
            operation_id=record.operation_id,
            stage_number=record.stage_number,
            status=record.status,
            executed_query_ids=tuple(record.executed_query_ids_json),
            retrieved_candidate_count=record.retrieved_candidate_count,
            admitted_candidate_count=record.admitted_candidate_count,
            visible_candidate_count=record.visible_candidate_count,
            timings=record.timings_json,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )


def get_search_run_report(run_id: str, *, database_url: str) -> dict[str, object] | None:
    """Read the complete private report for one durable search run."""

    with session_scope(database_url) as session:
        run = session.get(SearchRunRecordModel, run_id)
        if run is None:
            return None
        stages = session.scalars(
            select(SearchRunStageRecordModel)
            .where(SearchRunStageRecordModel.run_id == run_id)
            .order_by(SearchRunStageRecordModel.stage_number)
        ).all()
        outcomes = session.scalars(
            select(SearchRunProviderOutcomeRecordModel)
            .where(SearchRunProviderOutcomeRecordModel.run_id == run_id)
            .order_by(
                SearchRunProviderOutcomeRecordModel.stage_number,
                SearchRunProviderOutcomeRecordModel.source,
                SearchRunProviderOutcomeRecordModel.channel,
                SearchRunProviderOutcomeRecordModel.attempt,
            )
        ).all()
        candidates = session.scalars(
            select(SearchRunRankingCandidateRecordModel)
            .where(SearchRunRankingCandidateRecordModel.run_id == run_id)
            .order_by(
                SearchRunRankingCandidateRecordModel.stage_number,
                SearchRunRankingCandidateRecordModel.rank_position,
            )
        ).all()
        labels = session.scalars(
            select(SearchRunRankingLabelRecordModel)
            .where(SearchRunRankingLabelRecordModel.run_id == run_id)
            .order_by(SearchRunRankingLabelRecordModel.updated_at)
        ).all()
        return {
            "run": {
                "runId": run.run_id,
                "ownerUserId": run.owner_user_id,
                "topicDescription": run.topic_description,
                "status": run.status,
                "plannerMode": run.planner_mode,
                "plannerModel": run.planner_model,
                "rankingPolicyVersion": run.ranking_policy_version,
                "backendRevision": run.backend_revision,
                "partial": run.partial,
                "errorCode": run.error_code,
                "errorMessage": run.error_message,
                "createdAt": run.created_at.isoformat(),
                "startedAt": run.started_at.isoformat() if run.started_at else None,
                "completedAt": run.completed_at.isoformat() if run.completed_at else None,
            },
            "stages": [
                {
                    "stageNumber": stage.stage_number,
                    "operationId": stage.operation_id,
                    "status": stage.status,
                    "executedQueries": stage.executed_query_ids_json,
                    "candidateCounts": {
                        "retrieved": stage.retrieved_candidate_count,
                        "admitted": stage.admitted_candidate_count,
                        "visible": stage.visible_candidate_count,
                    },
                    "timings": stage.timings_json,
                }
                for stage in stages
            ],
            "providerOutcomes": [
                {
                    "stageNumber": outcome.stage_number,
                    "source": outcome.source,
                    "channel": outcome.channel,
                    "query": outcome.query_id,
                    "attempt": outcome.attempt,
                    "status": outcome.status,
                    "candidateCount": outcome.candidate_count,
                    "durationMs": outcome.duration_ms,
                    "retryAfterSeconds": outcome.retry_after_seconds,
                    "errorCode": outcome.error_code,
                    "errorMessage": outcome.error_message,
                }
                for outcome in outcomes
            ],
            "rankingSnapshots": [
                {
                    "stageNumber": candidate.stage_number,
                    "repositoryId": candidate.repository_id,
                    "repositorySource": candidate.repository_source,
                    "rankPosition": candidate.rank_position,
                    "finalScore": candidate.final_score,
                    "candidateFacts": candidate.candidate_facts_json,
                    "retrievalFacts": candidate.retrieval_facts_json,
                    "admissionFacts": candidate.admission_facts_json,
                    "rankingFeatures": candidate.ranking_features_json,
                    "scoreBreakdown": candidate.score_breakdown_json,
                }
                for candidate in candidates
            ],
            "labels": [
                {
                    "repositoryId": label.repository_id,
                    "userId": label.user_id,
                    "stageNumber": label.stage_number,
                    "label": label.label,
                    "updatedAt": label.updated_at.isoformat(),
                }
                for label in labels
            ],
        }


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


def _to_search_run_operation(
    record: SearchRunOperationRecordModel,
) -> SearchRunOperation:
    return SearchRunOperation(
        operation_id=record.operation_id,
        run_id=record.run_id,
        kind=record.kind,  # type: ignore[arg-type]
        status=record.status,  # type: ignore[arg-type]
        queued_at=record.queued_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        lease_holder_id=record.lease_holder_id,
        lease_expires_at=record.lease_expires_at,
        error_code=record.error_code,
        error_message=record.error_message,
    )

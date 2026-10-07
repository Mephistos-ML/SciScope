"""Durable background orchestration for Explore search runs."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import logging
import secrets
from uuid import uuid4

from app import config
from app.models.search_run import (
    SearchRun,
    SearchRunOperation,
    SearchRunProviderOutcome,
    SearchRunStage,
    SearchStageReport,
)
from app.services.search.access import hash_explore_topic
from app.services.search.explore.execution import (
    ExploreSearchExecution,
    deserialize_execution,
    serialize_execution,
)
from app.services.search.explore.service import (
    AiSearchPlanningError,
    ExploreSearchUnavailableError,
    expand_explore_search,
    run_explore_search,
)
from app.services.search.observability.context import SearchLogContext, build_request_id
from app.storage.search_runs import (
    create_search_run,
    create_search_run_operation,
    count_search_run_stages,
    get_search_run,
    record_search_run_provider_outcomes,
    record_search_run_ranking_candidates,
    record_search_run_stage,
    update_search_run,
    update_search_run_operation,
)

logger = logging.getLogger(__name__)


def create_explore_search_run(
    *,
    topic_description: str,
    owner_user_id: str | None = None,
    database_url: str,
) -> dict[str, object]:
    """Create a durable logical run with one queued initial operation."""
    now = datetime.now(UTC)
    run_id, operation_id = uuid4().hex, uuid4().hex
    guest_access_token = secrets.token_urlsafe(32) if owner_user_id is None else None
    run = SearchRun(
        run_id=run_id,
        owner_user_id=owner_user_id,
        topic_description=topic_description,
        topic_hash=hash_explore_topic(topic_description),
        status="queued",
        planner_mode=config.AI_PLANNER_MODE,
        planner_model=(
            config.OPENAI_MODEL if config.AI_PLANNER_MODE == "openai" else None
        ),
        planner_reasoning_effort=(
            config.OPENAI_REASONING_EFFORT
            if config.AI_PLANNER_MODE == "openai"
            else None
        ),
        ranking_policy_version="heuristic-v1",
        backend_revision="unknown",
        created_at=now,
        guest_access_token_hash=(
            _hash_guest_token(guest_access_token) if guest_access_token else None
        ),
    )
    create_search_run(run, database_url=database_url)
    create_search_run_operation(
        SearchRunOperation(operation_id, run_id, "initial", "queued", now),
        database_url=database_url,
    )
    payload = _build_run_snapshot(run)
    if guest_access_token is not None:
        payload["guestAccessToken"] = guest_access_token
    return payload


def get_explore_search_run(
    run_id: str,
    *,
    viewer_user_id: str | None,
    guest_access_token: str | None = None,
    database_url: str,
) -> dict[str, object] | None:
    """Read a run snapshot from the durable store."""
    run = get_search_run(run_id, database_url=database_url)
    if run is None or not _can_access_run(run, viewer_user_id, guest_access_token):
        return None
    return _build_run_snapshot(run)


def _can_access_run(
    run: SearchRun, viewer_user_id: str | None, guest_access_token: str | None,
) -> bool:
    if run.owner_user_id is not None:
        return run.owner_user_id == viewer_user_id
    if not run.guest_access_token_hash or not guest_access_token:
        return False
    return secrets.compare_digest(run.guest_access_token_hash, _hash_guest_token(guest_access_token))


def _hash_guest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_run_snapshot(run: SearchRun) -> dict[str, object]:
    payload = deepcopy(run.response_payload) if run.response_payload else {
        "topicDescription": run.topic_description,
        "aiSearchPlan": {"status": "pending", "queries": []},
        "items": [],
        "sourceStatuses": [],
        "canExpand": False,
    }
    payload.update(
        {
            "runId": run.run_id,
            "status": run.status,
            "error": run.error_message,
            "message": payload.get("message"),
            "createdAt": run.created_at.isoformat(),
            "updatedAt": (
                run.completed_at or run.started_at or run.created_at
            ).isoformat(),
        }
    )
    return payload


def expand_explore_search_run(
    run_id: str,
    *,
    viewer_user_id: str | None,
    guest_access_token: str | None = None,
    database_url: str,
) -> dict[str, object] | None:
    """Schedule one expansion against a completed durable run."""
    run = get_search_run(run_id, database_url=database_url)
    if run is None or not _can_access_run(run, viewer_user_id, guest_access_token):
        return None
    if run.status not in {"completed", "completed_partial"}:
        raise ValueError("Explore search run is not ready to expand.")
    execution = _load_execution(run.execution_state)
    if not isinstance(execution, ExploreSearchExecution) or not execution.pending_queries:
        raise ValueError("Explore search run has no more planned queries.")
    operation_id = uuid4().hex
    create_search_run_operation(
        SearchRunOperation(
            operation_id,
            run_id,
            "expansion",
            "queued",
            datetime.now(UTC),
        ),
        database_url=database_url,
    )
    update_search_run(run_id, status="running", database_url=database_url)
    return get_explore_search_run(
        run_id, viewer_user_id=viewer_user_id, guest_access_token=guest_access_token,
        database_url=database_url,
    )


def execute_search_run_operation(
    operation: SearchRunOperation,
    *,
    database_url: str,
) -> None:
    """Execute one leased operation selected by the worker composition boundary."""

    run = get_search_run(operation.run_id, database_url=database_url)
    if run is None:
        logger.error("Claimed search operation refers to a missing run: %s", operation.operation_id)
        return
    if run.status in {"completed", "completed_partial", "failed", "interrupted"}:
        update_search_run_operation(
            operation.operation_id,
            status=run.status,
            error_code=run.error_code,
            error_message=run.error_message,
            completed_at=run.completed_at or datetime.now(UTC),
            database_url=database_url,
        )
        return
    if operation.kind == "initial":
        _run_initial_search_run(
            run_id=run.run_id,
            operation_id=operation.operation_id,
            topic_description=run.topic_description,
            database_url=database_url,
        )
        return
    _run_search_expansion(
        run_id=run.run_id,
        operation_id=operation.operation_id,
        topic_description=run.topic_description,
        database_url=database_url,
    )


def _run_initial_search_run(
    *,
    run_id: str,
    operation_id: str,
    topic_description: str,
    database_url: str,
) -> None:
    now = datetime.now(UTC)
    update_search_run(
        run_id,
        status="running",
        started_at=now,
        database_url=database_url,
    )
    update_search_run_operation(
        operation_id,
        status="running",
        started_at=now,
        database_url=database_url,
    )
    try:
        payload = run_explore_search(
            topic_description=topic_description,
            database_url=database_url,
            execution_callback=lambda value: _store_execution(
                run_id,
                value,
                database_url,
            ),
            log_context=_build_log_context(
                topic_description,
                None,
            ).with_run_id(run_id),
            stage_report_callback=lambda report: _record_stage_report(
                run_id=run_id,
                operation_id=operation_id,
                stage_number=1,
                report=report,
                started_at=now,
                database_url=database_url,
            ),
        )
    except ExploreSearchUnavailableError as exc:
        _fail(run_id, operation_id, str(exc), database_url, exc.source_statuses)
        return
    except AiSearchPlanningError as exc:
        _fail(run_id, operation_id, str(exc), database_url)
        return
    except Exception:
        logger.exception("Explore search run crashed unexpectedly.")
        _fail(run_id, operation_id, "Explore search failed unexpectedly.", database_url)
        return
    _complete(run_id, operation_id, payload, database_url)


def _run_search_expansion(
    *,
    run_id: str,
    operation_id: str,
    topic_description: str,
    database_url: str,
) -> None:
    run = get_search_run(run_id, database_url=database_url)
    execution = _load_execution(run.execution_state if run else None)
    if not isinstance(execution, ExploreSearchExecution):
        _fail(run_id, operation_id, "Search execution state is unavailable.", database_url)
        return
    update_search_run_operation(
        operation_id,
        status="running",
        started_at=datetime.now(UTC),
        database_url=database_url,
    )
    stage_number = count_search_run_stages(run_id, database_url=database_url) + 1
    stage_started_at = datetime.now(UTC)
    try:
        payload = expand_explore_search(
            topic_description=topic_description,
            execution=execution,
            database_url=database_url,
            execution_callback=lambda value: _store_execution(run_id, value, database_url),
            log_context=_build_log_context(topic_description, None).with_run_id(run_id),
            stage_report_callback=lambda report: _record_stage_report(
                run_id=run_id,
                operation_id=operation_id,
                stage_number=stage_number,
                report=report,
                started_at=stage_started_at,
                database_url=database_url,
            ),
        )
    except Exception:
        logger.exception("Explore search expansion crashed unexpectedly.")
        _fail(run_id, operation_id, "Could not load another search angle.", database_url)
        return
    _complete(run_id, operation_id, payload, database_url)


def _complete(
    run_id: str,
    operation_id: str,
    payload: dict[str, object],
    database_url: str,
) -> None:
    now = datetime.now(UTC)
    status = "completed_partial" if payload.get("partial") else "completed"
    update_search_run(
        run_id,
        status=status,
        partial=status == "completed_partial",
        response_payload=payload,
        completed_at=now,
        database_url=database_url,
    )
    update_search_run_operation(
        operation_id,
        status=status,
        completed_at=now,
        database_url=database_url,
    )


def _record_stage_report(
    *,
    run_id: str,
    operation_id: str,
    stage_number: int,
    report: SearchStageReport,
    started_at: datetime,
    database_url: str,
) -> None:
    """Persist a completed stage and its provider lane outcomes."""

    completed_at = datetime.now(UTC)
    record_search_run_stage(
        SearchRunStage(
            run_id=run_id,
            operation_id=operation_id,
            stage_number=stage_number,
            status="completed",
            executed_query_ids=report.executed_queries,
            retrieved_candidate_count=report.retrieved_candidate_count,
            admitted_candidate_count=report.admitted_candidate_count,
            visible_candidate_count=report.visible_candidate_count,
            timings=report.timings,
            started_at=started_at,
            completed_at=completed_at,
        ),
        database_url=database_url,
    )
    record_search_run_provider_outcomes(
        tuple(
            SearchRunProviderOutcome(
                outcome_id=uuid4().hex,
                run_id=run_id,
                operation_id=operation_id,
                stage_number=stage_number,
                source=outcome.source,
                channel=outcome.channel,
                query_id=outcome.query,
                attempt=outcome.attempt,
                status=outcome.status,
                candidate_count=outcome.candidate_count,
                duration_ms=outcome.duration_ms,
                retry_after_seconds=outcome.retry_after_seconds,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
            )
            for outcome in report.provider_outcomes
        ),
        database_url=database_url,
    )
    record_search_run_ranking_candidates(
        run_id,
        stage_number,
        report.ranking_candidates,
        database_url=database_url,
    )


def _fail(
    run_id: str,
    operation_id: str,
    message: str,
    database_url: str,
    source_statuses: tuple[dict[str, object], ...] = (),
) -> None:
    now = datetime.now(UTC)
    update_search_run(
        run_id,
        status="failed",
        error_code="search_failed",
        error_message=message,
        response_payload=(
            {"sourceStatuses": list(source_statuses)} if source_statuses else None
        ),
        completed_at=now,
        database_url=database_url,
    )
    update_search_run_operation(
        operation_id,
        status="failed",
        error_code="search_failed",
        error_message=message,
        completed_at=now,
        database_url=database_url,
    )


def _store_execution(
    run_id: str,
    value: ExploreSearchExecution,
    database_url: str,
) -> None:
    update_search_run(
        run_id,
        status="running",
        execution_state=serialize_execution(value),
        database_url=database_url,
    )


def _load_execution(
    execution_state: dict[str, object] | None,
) -> ExploreSearchExecution | None:
    if execution_state is None:
        return None
    try:
        execution = deserialize_execution(execution_state)
    except (KeyError, TypeError, ValueError):
        logger.exception("Stored Explore execution state is invalid.")
        return None
    return execution


def _build_log_context(
    topic_description: str,
    value: SearchLogContext | None,
) -> SearchLogContext:
    return value or SearchLogContext(
        request_id=build_request_id(),
        topic_hash=hash_explore_topic(topic_description),
    )

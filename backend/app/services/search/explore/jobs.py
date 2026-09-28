"""Durable background orchestration for Explore search runs."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import logging
import threading
from uuid import uuid4

from app import config
from app.models.search_run import (
    SearchRun,
    SearchRunOperation,
    SearchRunProviderOutcome,
    SearchRunStage,
    SearchStageReport,
)
from app.runtime.state import STATE
from app.services.search.access import hash_explore_topic
from app.services.search.explore.execution import (
    ExploreSearchExecution,
    deserialize_execution,
    serialize_execution,
)
from app.services.search.explore.response import ExploreResponseMode
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
    record_search_run_stage,
    update_search_run,
    update_search_run_operation,
)

logger = logging.getLogger(__name__)


def create_explore_search_job(
    *,
    topic_description: str,
    response_mode: ExploreResponseMode = "canonical",
    owner_user_id: str | None = None,
    log_context: SearchLogContext | None = None,
    database_url: str,
) -> dict[str, object]:
    """Create a durable logical run and schedule its initial operation."""
    now = datetime.now(UTC)
    run_id, operation_id = uuid4().hex, uuid4().hex
    create_search_run(
        SearchRun(
            run_id,
            owner_user_id,
            topic_description,
            hash_explore_topic(topic_description),
            response_mode,
            "queued",
            config.AI_PLANNER_MODE,
            None,
            "heuristic-v1",
            "unknown",
            now,
        ),
        database_url=database_url,
    )
    create_search_run_operation(
        SearchRunOperation(operation_id, run_id, "initial", "queued", now),
        database_url=database_url,
    )
    _start_explore_search_job_runner(
        job_id=run_id,
        operation_id=operation_id,
        topic_description=topic_description,
        response_mode=response_mode,
        database_url=database_url,
        log_context=_build_log_context(topic_description, log_context).with_job_id(run_id),
    )
    return get_explore_search_job(run_id, database_url=database_url) or {}


def get_explore_search_job(
    job_id: str,
    *,
    database_url: str,
) -> dict[str, object] | None:
    """Read a run snapshot from the durable store."""
    run = get_search_run(job_id, database_url=database_url)
    if run is None:
        return None
    payload = deepcopy(run.response_payload) if run.response_payload else {
        "topicDescription": run.topic_description,
        "aiSearchPlan": {"status": "pending", "queries": []},
        "items": [],
        "sourceStatuses": [],
        "canExpand": False,
    }
    payload.update(
        {
            "jobId": run.run_id,
            "status": run.status,
            "error": run.error_message,
            "message": payload.get("message"),
            "responseMode": run.response_mode,
            "ownerUserId": run.owner_user_id,
            "createdAt": run.created_at.isoformat(),
            "updatedAt": (
                run.completed_at or run.started_at or run.created_at
            ).isoformat(),
        }
    )
    return payload


def expand_explore_search_job(
    job_id: str,
    *,
    database_url: str,
) -> dict[str, object] | None:
    """Schedule one expansion against a completed durable run."""
    run = get_search_run(job_id, database_url=database_url)
    if run is None:
        return None
    if run.status not in {"completed", "completed_partial"}:
        raise ValueError("Explore search job is not ready to expand.")
    execution = _load_execution(job_id, run.execution_state)
    if not isinstance(execution, ExploreSearchExecution) or not execution.pending_queries:
        raise ValueError("Explore search job has no more planned queries.")
    operation_id = uuid4().hex
    create_search_run_operation(
        SearchRunOperation(
            operation_id,
            job_id,
            "expansion",
            "queued",
            datetime.now(UTC),
        ),
        database_url=database_url,
    )
    update_search_run(job_id, status="running", database_url=database_url)
    _start_explore_search_expansion_runner(
        job_id=job_id,
        operation_id=operation_id,
        topic_description=run.topic_description,
        response_mode=run.response_mode,
        database_url=database_url,
    )
    return get_explore_search_job(job_id, database_url=database_url)


def _start_explore_search_job_runner(**kwargs: object) -> None:
    threading.Thread(target=lambda: _run_explore_search_job(**kwargs), daemon=True).start()


def _run_explore_search_job(
    *,
    job_id: str,
    operation_id: str,
    topic_description: str,
    response_mode: ExploreResponseMode,
    database_url: str,
    log_context: SearchLogContext | None = None,
) -> None:
    now = datetime.now(UTC)
    update_search_run(
        job_id,
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
            response_mode=response_mode,
            database_url=database_url,
            execution_callback=lambda value: _store_execution(
                job_id,
                value,
                database_url,
            ),
            log_context=_build_log_context(
                topic_description,
                log_context,
            ).with_job_id(job_id),
            stage_report_callback=lambda report: _record_stage_report(
                job_id=job_id,
                operation_id=operation_id,
                stage_number=1,
                report=report,
                started_at=now,
                database_url=database_url,
            ),
        )
    except ExploreSearchUnavailableError as exc:
        _fail(job_id, operation_id, str(exc), database_url, exc.source_statuses)
        return
    except AiSearchPlanningError as exc:
        _fail(job_id, operation_id, str(exc), database_url)
        return
    except Exception:
        logger.exception("Explore search run crashed unexpectedly.")
        _fail(job_id, operation_id, "Explore search failed unexpectedly.", database_url)
        return
    _complete(job_id, operation_id, payload, database_url)


def _start_explore_search_expansion_runner(**kwargs: object) -> None:
    threading.Thread(
        target=lambda: _run_explore_search_expansion_job(**kwargs),
        daemon=True,
    ).start()


def _run_explore_search_expansion_job(
    *,
    job_id: str,
    operation_id: str,
    topic_description: str,
    response_mode: ExploreResponseMode,
    database_url: str,
) -> None:
    run = get_search_run(job_id, database_url=database_url)
    execution = _load_execution(job_id, run.execution_state if run else None)
    if not isinstance(execution, ExploreSearchExecution):
        _fail(job_id, operation_id, "Search execution state is unavailable.", database_url)
        return
    update_search_run_operation(
        operation_id,
        status="running",
        started_at=datetime.now(UTC),
        database_url=database_url,
    )
    stage_number = count_search_run_stages(job_id, database_url=database_url) + 1
    stage_started_at = datetime.now(UTC)
    try:
        payload = expand_explore_search(
            topic_description=topic_description,
            execution=execution,
            response_mode=response_mode,
            database_url=database_url,
            execution_callback=lambda value: _store_execution(job_id, value, database_url),
            log_context=_build_log_context(topic_description, None).with_job_id(job_id),
            stage_report_callback=lambda report: _record_stage_report(
                job_id=job_id,
                operation_id=operation_id,
                stage_number=stage_number,
                report=report,
                started_at=stage_started_at,
                database_url=database_url,
            ),
        )
    except Exception:
        logger.exception("Explore search expansion crashed unexpectedly.")
        _fail(job_id, operation_id, "Could not load another search angle.", database_url)
        return
    _complete(job_id, operation_id, payload, database_url)


def _complete(
    job_id: str,
    operation_id: str,
    payload: dict[str, object],
    database_url: str,
) -> None:
    now = datetime.now(UTC)
    status = "completed_partial" if payload.get("partial") else "completed"
    update_search_run(
        job_id,
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
    job_id: str,
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
            run_id=job_id,
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
                run_id=job_id,
                operation_id=operation_id,
                stage_number=stage_number,
                source=outcome.source,
                channel=outcome.channel,
                query_id=outcome.query,
                attempt=outcome.attempt,
                status=outcome.status,
                candidate_count=outcome.candidate_count,
                duration_ms=outcome.duration_ms,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
            )
            for outcome in report.provider_outcomes
        ),
        database_url=database_url,
    )
def _fail(
    job_id: str,
    operation_id: str,
    message: str,
    database_url: str,
    source_statuses: tuple[dict[str, object], ...] = (),
) -> None:
    now = datetime.now(UTC)
    update_search_run(
        job_id,
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
    job_id: str,
    value: ExploreSearchExecution,
    database_url: str,
) -> None:
    with STATE.explore_search_jobs_lock:
        STATE.explore_search_jobs[job_id] = {"_execution": value}
    update_search_run(
        job_id,
        status="running",
        execution_state=serialize_execution(value),
        database_url=database_url,
    )


def _load_execution(
    job_id: str,
    execution_state: dict[str, object] | None,
) -> ExploreSearchExecution | None:
    with STATE.explore_search_jobs_lock:
        cached = STATE.explore_search_jobs.get(job_id, {}).get("_execution")
    if isinstance(cached, ExploreSearchExecution):
        return cached
    if execution_state is None:
        return None
    try:
        execution = deserialize_execution(execution_state)
    except (KeyError, TypeError, ValueError):
        logger.exception("Stored Explore execution state is invalid.")
        return None
    with STATE.explore_search_jobs_lock:
        STATE.explore_search_jobs[job_id] = {"_execution": execution}
    return execution


def _build_log_context(
    topic_description: str,
    value: SearchLogContext | None,
) -> SearchLogContext:
    return value or SearchLogContext(
        request_id=build_request_id(),
        topic_hash=hash_explore_topic(topic_description),
    )

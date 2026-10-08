"""Durable background orchestration for Explore search runs."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import logging
import secrets
from uuid import uuid4

from app.models.explore_access import ExploreAdmission
from app.models.search_run import (
    SearchRun,
    SearchRunOperation,
    SearchRunStatus,
    SearchStageReport,
)
from app.services.search.access.service import hash_explore_topic, record_explore_admission
from app.services.search.access.errors import ExploreAccessDeniedError
from app.storage.search_admission import explore_admission_transaction
from app.services.search.explore.dependencies import ExploreDependencies
from app.services.search.explore.execution import (
    ExploreSearchExecution,
    ExploreExecutionStateError,
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
    SearchRunLeaseLostError,
    finish_search_run_operation,
    get_search_run,
    start_search_run_operation,
)

logger = logging.getLogger(__name__)


def create_explore_search_run(
    *,
    topic_description: str,
    admission: ExploreAdmission,
    dependencies: ExploreDependencies,
    database_url: str,
) -> dict[str, object]:
    """Atomically admit a logical run and queue its initial operation."""
    now = datetime.now(UTC)
    run_id, operation_id = uuid4().hex, uuid4().hex
    owner_user_id = admission.actor.user_id
    guest_access_token = secrets.token_urlsafe(32) if owner_user_id is None else None
    run = SearchRun(
        run_id=run_id,
        owner_user_id=owner_user_id,
        topic_description=topic_description,
        topic_hash=hash_explore_topic(topic_description),
        status="queued",
        planner_mode=dependencies.planner.identity.mode,
        planner_model=dependencies.planner.identity.model,
        planner_reasoning_effort=dependencies.planner.identity.reasoning_effort,
        ranking_policy_version="heuristic-v1",
        backend_revision="unknown",
        created_at=now,
        guest_access_token_hash=(
            _hash_guest_token(guest_access_token) if guest_access_token else None
        ),
    )
    with explore_admission_transaction(database_url=database_url) as store:
        decision = record_explore_admission(
            admission.actor, store=store, topic_hash=run.topic_hash,
            turnstile_verified=admission.turnstile_verified,
            bypass_quota=admission.bypass_quota,
        )
        if decision.allowed:
            store.schedule_initial_run(run, operation_id=operation_id)

    if not decision.allowed:
        raise ExploreAccessDeniedError(decision)
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
    prepare_admission: Callable[[str], ExploreAdmission],
    database_url: str,
) -> dict[str, object] | None:
    """Atomically admit and schedule one expansion against a completed run."""
    run = get_search_run(run_id, database_url=database_url)
    if run is None or not _can_access_run(run, viewer_user_id, guest_access_token):
        return None
    _require_expandable_run(run)
    admission = prepare_admission(run.topic_description)

    with explore_admission_transaction(database_url=database_url) as store:
        run = store.get_run(run_id)
        if run is None or not _can_access_run(run, viewer_user_id, guest_access_token):
            return None
        _require_expandable_run(run)
        decision = record_explore_admission(
            admission.actor, store=store, topic_hash=run.topic_hash,
            turnstile_verified=admission.turnstile_verified,
            bypass_quota=admission.bypass_quota,
        )
        if decision.allowed:
            store.schedule_expansion(
                run_id=run_id, operation_id=uuid4().hex, queued_at=datetime.now(UTC),
            )

    if not decision.allowed:
        raise ExploreAccessDeniedError(decision)
    return get_explore_search_run(
        run_id, viewer_user_id=viewer_user_id, guest_access_token=guest_access_token,
        database_url=database_url,
    )


def _require_expandable_run(run: SearchRun) -> None:
    """Reject a lifecycle conflict before consuming capacity."""
    if run.status not in {"completed", "completed_partial"}:
        raise ValueError("Explore search run is not ready to expand.")
    execution = deserialize_execution(run.execution_state)
    if not execution.pending_queries:
        raise ValueError("Explore search run has no more planned queries.")


def execute_search_run_operation(
    operation: SearchRunOperation,
    *,
    dependencies: ExploreDependencies,
    ensure_lease: Callable[[], None],
    database_url: str,
) -> None:
    """Replay a leased operation and atomically publish its complete outcome."""
    ensure_lease()
    run = start_search_run_operation(
        operation,
        planner_identity=dependencies.planner.identity if operation.kind == "initial" else None,
        database_url=database_url,
    )
    ensure_lease()
    if run.status in {"completed", "completed_partial", "failed", "interrupted"}:
        finish_search_run_operation(
            operation,
            status=run.status,
            error_code=run.error_code,
            error_message=run.error_message,
            database_url=database_url,
        )
        return

    # Callbacks collect attempt-local facts. Advancing the durable replay baseline
    # before committing the result would skip work after a crash or takeover.
    execution_state: dict[str, object] | None = None
    report: SearchStageReport | None = None
    started_at = datetime.now(UTC)

    def remember_execution(value: ExploreSearchExecution) -> None:
        nonlocal execution_state
        ensure_lease()
        execution_state = serialize_execution(value)

    def remember_report(value: SearchStageReport) -> None:
        nonlocal report
        ensure_lease()
        report = value

    payload: dict[str, object] | None = None
    message: str | None = None
    status: SearchRunStatus = "failed"
    error_code = "search_failed"
    try:
        if operation.kind == "initial":
            payload = run_explore_search(
                dependencies=dependencies,
                topic_description=run.topic_description,
                database_url=database_url,
                execution_callback=remember_execution,
                stage_report_callback=remember_report,
                log_context=_build_log_context(run.topic_description, None).with_run_id(run.run_id),
            )
        else:
            baseline = deserialize_execution(run.execution_state)
            payload = expand_explore_search(
                dependencies=dependencies,
                topic_description=run.topic_description,
                execution=baseline,
                database_url=database_url,
                execution_callback=remember_execution,
                stage_report_callback=remember_report,
                log_context=_build_log_context(run.topic_description, None).with_run_id(run.run_id),
            )
        if payload is not None:
            status = "completed_partial" if payload.get("partial") else "completed"
    except SearchRunLeaseLostError:
        raise
    except ExploreExecutionStateError as exc:
        error_code = exc.code
        message = str(exc)
        logger.warning("Cannot resume Explore operation %s: %s", operation.operation_id, exc.code)
    except ExploreSearchUnavailableError as exc:
        message = str(exc)
        payload = {"sourceStatuses": list(exc.source_statuses)} if exc.source_statuses else None
    except AiSearchPlanningError as exc:
        message = str(exc)
    except Exception:
        logger.exception("Explore search operation crashed unexpectedly: %s", operation.operation_id)
        message = (
            "Explore search failed unexpectedly."
            if operation.kind == "initial"
            else "Could not load another search angle."
        )

    ensure_lease()
    # Persistence failures propagate: the unchanged baseline remains retryable.
    finish_search_run_operation(
        operation,
        status=status,
        response_payload=payload,
        execution_state=execution_state,
        stage_report=report,
        stage_started_at=started_at,
        error_code=error_code if status == "failed" else None,
        error_message=message,
        database_url=database_url,
    )


def _build_log_context(
    topic_description: str,
    value: SearchLogContext | None,
) -> SearchLogContext:
    return value or SearchLogContext(
        request_id=build_request_id(),
        topic_hash=hash_explore_topic(topic_description),
    )

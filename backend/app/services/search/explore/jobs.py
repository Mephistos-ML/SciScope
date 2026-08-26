"""Background job orchestration for Explore searches."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import logging
import threading
from time import monotonic
from uuid import uuid4

from app import config
from app.runtime.state import STATE
from app.services.search.explore.service import (
    AiSearchPlanningError,
    ExploreSearchUnavailableError,
    run_explore_search,
)

logger = logging.getLogger(__name__)

JOB_TERMINAL_STATUSES = {"completed", "completed_partial", "failed"}
MAX_EXPLORE_SEARCH_JOBS = 100
MAX_COMPLETED_JOB_AGE = timedelta(hours=12)


def create_explore_search_job(*, topic_description: str) -> dict[str, object]:
    """Create one background Explore search job and return its initial snapshot."""

    now = _now_isoformat()
    job_id = uuid4().hex
    snapshot = {
        "jobId": job_id,
        "status": "queued",
        "topicDescription": topic_description,
        "aiSearchPlan": {"status": "pending", "queries": []},
        "items": [],
        "sourceStatuses": [],
        "error": None,
        "message": None,
        "createdAt": now,
        "updatedAt": now,
    }

    with STATE.explore_search_jobs_lock:
        _prune_explore_search_jobs()
        STATE.explore_search_jobs[job_id] = snapshot

    _start_explore_search_job_runner(job_id=job_id, topic_description=topic_description)
    return get_explore_search_job(job_id) or deepcopy(snapshot)


def get_explore_search_job(job_id: str) -> dict[str, object] | None:
    """Return one immutable snapshot for an Explore search job."""

    with STATE.explore_search_jobs_lock:
        snapshot = STATE.explore_search_jobs.get(job_id)
        if snapshot is None:
            return None
        return deepcopy(snapshot)


def _start_explore_search_job_runner(*, job_id: str, topic_description: str) -> None:
    thread = threading.Thread(
        target=lambda: _run_explore_search_job(
            job_id=job_id,
            topic_description=topic_description,
        ),
        name=f"sciscope-explore-job-{job_id[:8]}",
        daemon=True,
    )
    thread.start()


def _run_explore_search_job(*, job_id: str, topic_description: str) -> None:
    started_at = monotonic()
    soft_deadline_monotonic = (
        started_at + config.EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS
    )
    hard_deadline_monotonic = (
        started_at + config.EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS
    )
    try:
        _update_explore_search_job(job_id, status="planning")
        payload = run_explore_search(
            topic_description=topic_description,
            progress_callback=lambda snapshot: _update_explore_search_job(
                job_id,
                status="retrieving",
                aiSearchPlan=snapshot["aiSearchPlan"],
                items=snapshot["items"],
                sourceStatuses=snapshot["sourceStatuses"],
                error=None,
                message=snapshot.get("message"),
            ),
            soft_deadline_monotonic=soft_deadline_monotonic,
            hard_deadline_monotonic=hard_deadline_monotonic,
        )
    except ExploreSearchUnavailableError as exc:
        logger.warning("Explore search job failed because every provider is unavailable.")
        _update_explore_search_job(
            job_id,
            status="failed",
            sourceStatuses=exc.source_statuses,
            error=str(exc),
            message=None,
        )
        return
    except AiSearchPlanningError as exc:
        logger.warning("Explore search job failed during AI planning: %s", exc)
        _update_explore_search_job(
            job_id,
            status="failed",
            error=str(exc),
            message=None,
        )
        return
    except Exception:
        logger.exception("Explore search job crashed unexpectedly.")
        _update_explore_search_job(
            job_id,
            status="failed",
            error="Explore search failed unexpectedly.",
            message=None,
        )
        return

    completed_status = "completed_partial" if payload.get("partial") else "completed"
    if completed_status == "completed_partial" and not payload["items"]:
        _update_explore_search_job(
            job_id,
            status="failed",
            sourceStatuses=payload["sourceStatuses"],
            error=str(
                payload.get("message")
                or "Search timed out before any results were returned."
            ),
            message=None,
        )
        return

    _update_explore_search_job(
        job_id,
        status=completed_status,
        aiSearchPlan=payload["aiSearchPlan"],
        items=payload["items"],
        sourceStatuses=payload["sourceStatuses"],
        error=None,
        message=payload.get("message"),
    )


def _update_explore_search_job(
    job_id: str,
    *,
    status: str,
    aiSearchPlan: dict[str, object] | None = None,
    items: list[dict[str, object]] | None = None,
    sourceStatuses: list[dict[str, object]] | None = None,
    error: str | None = None,
    message: str | None = None,
) -> None:
    with STATE.explore_search_jobs_lock:
        snapshot = STATE.explore_search_jobs.get(job_id)
        if snapshot is None:
            return

        snapshot["status"] = status
        snapshot["updatedAt"] = _now_isoformat()
        if aiSearchPlan is not None:
            snapshot["aiSearchPlan"] = deepcopy(aiSearchPlan)
        if items is not None:
            snapshot["items"] = deepcopy(items)
        if sourceStatuses is not None:
            snapshot["sourceStatuses"] = deepcopy(sourceStatuses)
        snapshot["error"] = error
        snapshot["message"] = message


def _prune_explore_search_jobs() -> None:
    if len(STATE.explore_search_jobs) < MAX_EXPLORE_SEARCH_JOBS:
        return

    cutoff = datetime.now(UTC) - MAX_COMPLETED_JOB_AGE
    removable_job_ids = [
        job_id
        for job_id, snapshot in STATE.explore_search_jobs.items()
        if str(snapshot.get("status") or "") in JOB_TERMINAL_STATUSES
        and _parse_job_timestamp(snapshot.get("updatedAt")) < cutoff
    ]
    for job_id in removable_job_ids:
        STATE.explore_search_jobs.pop(job_id, None)

    if len(STATE.explore_search_jobs) < MAX_EXPLORE_SEARCH_JOBS:
        return

    terminal_job_ids = [
        job_id
        for job_id, snapshot in STATE.explore_search_jobs.items()
        if str(snapshot.get("status") or "") in JOB_TERMINAL_STATUSES
    ]
    sorted_job_ids = sorted(
        terminal_job_ids,
        key=lambda job_id: _parse_job_timestamp(
            STATE.explore_search_jobs[job_id].get("updatedAt")
        ),
    )
    overflow = min(
        len(sorted_job_ids),
        len(STATE.explore_search_jobs) - MAX_EXPLORE_SEARCH_JOBS + 1,
    )
    for job_id in sorted_job_ids[:overflow]:
        STATE.explore_search_jobs.pop(job_id, None)


def _parse_job_timestamp(value: object) -> datetime:
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=UTC)


def _now_isoformat() -> str:
    return datetime.now(UTC).isoformat()

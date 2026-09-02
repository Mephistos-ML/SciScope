"""Parallel lane execution helpers for external retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from collections.abc import Sequence
from queue import Queue
import threading
from time import monotonic
from typing import Callable

from app.models.signal import Signal
from app.services.search.observability import (
    SearchLogContext,
    build_duration_ms,
    log_search_event,
)
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval.models import RetrievedCandidates, RetrievalHit
from app.services.search.retrieval.timeouts import is_deadline_reached
from app.sources.common import RepositorySourceError, build_source_status

logger = logging.getLogger(__name__)

RepositoryDiscoverer = Callable[[Sequence[str]], list[Signal]]
RetrievalProgressCallback = Callable[[RetrievedCandidates], None]

SOURCE_DISPLAY_NAMES = {
    "github": "GitHub",
    "gitlab": "GitLab",
}


@dataclass(slots=True)
class LaneResult:
    source_name: str
    channel_name: str
    started_at_monotonic: float
    source_candidates: list[Signal] = field(default_factory=list)
    source_error: RepositorySourceError | None = None
    query_failures: tuple["QueryFailure", ...] = ()
    completed_query_count: int | None = None
    crashed: bool = False


@dataclass(frozen=True, slots=True)
class QueryFailure:
    """One failed query within an otherwise completed retrieval lane."""

    query: str
    error: RepositorySourceError


def start_lane_worker(
    *,
    source_name: str,
    channel_name: str,
    discover_candidates: RepositoryDiscoverer,
    supports_deadline: bool,
    queries: Sequence[str],
    deadline_monotonic: float | None,
    result_queue: Queue[LaneResult],
) -> None:
    """Start one retrieval lane in a background thread."""

    thread = threading.Thread(
        target=lambda: _run_lane_worker(
            source_name=source_name,
            channel_name=channel_name,
            discover_candidates=discover_candidates,
            supports_deadline=supports_deadline,
            queries=queries,
            deadline_monotonic=deadline_monotonic,
            result_queue=result_queue,
        ),
        name=f"sciscope-retrieval-{source_name}-{channel_name}",
        daemon=True,
    )
    thread.start()


def run_discoverer(
    discover_candidates: RepositoryDiscoverer,
    queries: Sequence[str],
    *,
    lane_deadline_monotonic: float | None,
    supports_deadline: bool,
) -> list[Signal]:
    """Run one provider discoverer with optional deadline support."""

    if not supports_deadline:
        return list(discover_candidates(queries))
    return list(
        discover_candidates(
            queries,
            deadline_monotonic=lane_deadline_monotonic,
        )
    )


def consume_lane_result(
    lane_result: LaneResult,
    *,
    queries: Sequence[str],
    candidates: list[RetrievalHit],
    source_statuses_by_source: dict[str, dict[str, object]],
    successful_sources: set[str],
    log_context: SearchLogContext | None,
) -> tuple[bool, str | None]:
    """Merge one completed lane result into retrieval state."""

    source_name = lane_result.source_name
    channel_name = lane_result.channel_name

    if lane_result.source_error is not None:
        exc = lane_result.source_error
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_retrieval_lane_failed",
                context=log_context,
                level=logging.WARNING,
                duration_ms=build_duration_ms(lane_result.started_at_monotonic),
                source=source_name,
                channel=channel_name,
                status=exc.status,
                query_count=len(queries),
                candidate_count=0,
                error_code=exc.status,
                error_message=exc.public_message,
            )
        merge_source_status(
            source_statuses_by_source,
            build_source_status(
                source=source_name,
                status=exc.status,
                candidate_count=0,
                error=exc.public_message,
            ),
        )
        return (
            True,
            f"{SOURCE_DISPLAY_NAMES[source_name]} {channel_name.replace('_', ' ')} returned {exc.status}.",
        )

    if lane_result.crashed:
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_retrieval_lane_failed",
                context=log_context,
                level=logging.ERROR,
                duration_ms=build_duration_ms(lane_result.started_at_monotonic),
                source=source_name,
                channel=channel_name,
                status="error",
                query_count=len(queries),
                candidate_count=0,
                error_code="unexpected_error",
                error_message=(
                    f"{SOURCE_DISPLAY_NAMES[source_name]} repository search is unavailable right now."
                ),
            )
        merge_source_status(
            source_statuses_by_source,
            build_source_status(
                source=source_name,
                status="error",
                candidate_count=0,
                error=(
                    f"{SOURCE_DISPLAY_NAMES[source_name]} repository search is "
                    "unavailable right now."
                ),
            ),
        )
        return (
            True,
            f"{SOURCE_DISPLAY_NAMES[source_name]} {channel_name.replace('_', ' ')} crashed.",
        )

    query_failures = lane_result.query_failures
    completed_query_count = lane_result.completed_query_count
    logger.info(
        (
            "Explore retrieval completed for source=%s channel=%s candidate_count=%s "
            "failed_query_count=%s"
        ),
        source_name,
        channel_name,
        len(lane_result.source_candidates),
        len(query_failures),
    )
    if log_context is not None:
        log_search_event(
            logger=logger,
            event="explore_retrieval_lane_completed",
            context=log_context,
            duration_ms=build_duration_ms(lane_result.started_at_monotonic),
            source=source_name,
            channel=channel_name,
            status="partial" if query_failures else "ok",
            query_count=len(queries),
            candidate_count=len(lane_result.source_candidates),
            completed_query_count=completed_query_count,
            failed_query_count=len(query_failures),
        )
        for query_failure in query_failures:
            log_search_event(
                logger=logger,
                event="explore_retrieval_query_failed",
                context=log_context,
                level=logging.WARNING,
                duration_ms=build_duration_ms(lane_result.started_at_monotonic),
                source=source_name,
                channel=channel_name,
                status=query_failure.error.status,
                query=query_failure.query,
                error_code=query_failure.error.status,
                error_message=query_failure.error.public_message,
            )
    lane_succeeded = completed_query_count is None or completed_query_count > 0
    if lane_succeeded:
        successful_sources.add(source_name)
    candidates.extend(
        RetrievalHit(
            source=source_name,
            channel=channel_name,
            query=str(signal.payload.get("query") or ""),
            rank=index,
            signal=signal,
        )
        for index, signal in enumerate(lane_result.source_candidates, start=1)
    )
    if lane_succeeded:
        merge_source_status(
            source_statuses_by_source,
            build_source_status(
                source=source_name,
                status="ok",
                candidate_count=len(lane_result.source_candidates),
                error=None,
            ),
        )
    else:
        first_failure = query_failures[0].error
        merge_source_status(
            source_statuses_by_source,
            build_source_status(
                source=source_name,
                status=first_failure.status,
                candidate_count=0,
                error=first_failure.public_message,
            ),
        )
    if not query_failures:
        return False, None

    warning = _build_query_failure_warning(
        source_name=source_name,
        channel_name=channel_name,
        query_failures=query_failures,
        completed_query_count=completed_query_count or 0,
    )
    return (
        True,
        warning,
    )


def emit_retrieval_progress(
    candidates: list[RetrievalHit],
    source_statuses_by_source: dict[str, dict[str, object]],
    successful_sources: set[str],
    progress_callback: RetrievalProgressCallback | None,
    *,
    partial: bool,
    warnings: list[str],
) -> None:
    """Emit one partial retrieval snapshot for UI polling."""

    if progress_callback is None:
        return

    progress_callback(
        RetrievedCandidates(
            candidates=merge_retrieval_hits(tuple(candidates)),
            source_statuses=tuple(source_statuses_by_source.values()),
            successful_source_count=len(successful_sources),
            partial=partial,
            warnings=tuple(warnings),
        )
    )


def merge_source_status(
    statuses_by_source: dict[str, dict[str, object]],
    incoming: dict[str, object],
) -> None:
    """Merge one source status into the aggregate source status map."""

    source_name = str(incoming.get("source") or "")
    if not source_name:
        return

    existing = statuses_by_source.get(source_name)
    if existing is None:
        statuses_by_source[source_name] = dict(incoming)
        return

    existing["candidateCount"] = int(existing.get("candidateCount") or 0) + int(
        incoming.get("candidateCount") or 0
    )
    if incoming.get("status") == "ok":
        existing["status"] = "ok"
        existing["error"] = None
        return

    if existing.get("status") == "ok":
        return

    existing["status"] = str(incoming.get("status") or existing.get("status") or "error")
    if not existing.get("error"):
        existing["error"] = incoming.get("error")


def _run_lane_worker(
    *,
    source_name: str,
    channel_name: str,
    discover_candidates: RepositoryDiscoverer,
    supports_deadline: bool,
    queries: Sequence[str],
    deadline_monotonic: float | None,
    result_queue: Queue[LaneResult],
) -> None:
    logger.info(
        "Explore retrieval started for source=%s channel=%s query_count=%s queries=%s",
        source_name,
        channel_name,
        len(queries),
        summarize_queries(queries),
    )
    lane_started_at = monotonic()
    try:
        source_candidates, query_failures, completed_query_count = _run_lane_discoverer(
            channel_name=channel_name,
            discover_candidates=discover_candidates,
            queries=queries,
            lane_deadline_monotonic=deadline_monotonic,
            supports_deadline=supports_deadline,
        )
    except RepositorySourceError as exc:
        logger.warning(
            (
                "Explore retrieval failed for source=%s channel=%s status=%s "
                "queries=%s message=%s"
            ),
            source_name,
            channel_name,
            exc.status,
            summarize_queries(queries),
            exc.public_message,
        )
        result_queue.put(
            LaneResult(
                source_name=source_name,
                channel_name=channel_name,
                started_at_monotonic=lane_started_at,
                source_error=exc,
            )
        )
        return
    except Exception:
        logger.exception(
            "Explore retrieval crashed for source=%s channel=%s queries=%s",
            source_name,
            channel_name,
            summarize_queries(queries),
        )
        result_queue.put(
            LaneResult(
                source_name=source_name,
                channel_name=channel_name,
                started_at_monotonic=lane_started_at,
                crashed=True,
            )
        )
        return

    result_queue.put(
        LaneResult(
            source_name=source_name,
            channel_name=channel_name,
            started_at_monotonic=lane_started_at,
            source_candidates=source_candidates,
            query_failures=query_failures,
            completed_query_count=completed_query_count,
        )
    )


def _run_lane_discoverer(
    *,
    channel_name: str,
    discover_candidates: RepositoryDiscoverer,
    queries: Sequence[str],
    lane_deadline_monotonic: float | None,
    supports_deadline: bool,
) -> tuple[list[Signal], tuple[QueryFailure, ...], int | None]:
    """Run a lane, retaining completed code-search queries after local failures."""

    if channel_name != "code_search":
        return (
            run_discoverer(
                discover_candidates,
                queries,
                lane_deadline_monotonic=lane_deadline_monotonic,
                supports_deadline=supports_deadline,
            ),
            (),
            None,
        )

    source_candidates: list[Signal] = []
    query_failures: list[QueryFailure] = []
    completed_query_count = 0
    for query in queries:
        try:
            source_candidates.extend(
                run_discoverer(
                    discover_candidates,
                    (query,),
                    lane_deadline_monotonic=lane_deadline_monotonic,
                    supports_deadline=supports_deadline,
                )
            )
            completed_query_count += 1
        except RepositorySourceError as exc:
            query_failures.append(QueryFailure(query=query, error=exc))
            if exc.status == "rate_limited" or is_deadline_reached(
                lane_deadline_monotonic
            ):
                break

    return source_candidates, tuple(query_failures), completed_query_count


def _build_query_failure_warning(
    *,
    source_name: str,
    channel_name: str,
    query_failures: tuple[QueryFailure, ...],
    completed_query_count: int,
) -> str:
    """Build one user-facing warning for a partially completed code-search lane."""

    display_name = SOURCE_DISPLAY_NAMES[source_name]
    channel_label = channel_name.replace("_", " ")
    rate_limit_failure = next(
        (
            failure
            for failure in query_failures
            if failure.error.status == "rate_limited"
        ),
        None,
    )
    if rate_limit_failure is not None:
        retry_message = _format_retry_after(
            rate_limit_failure.error.retry_after_seconds
        )
        return (
            f"{display_name} {channel_label} is rate-limited. {retry_message} "
            f"Retained results from {completed_query_count} completed queries."
        )

    failed_statuses = {failure.error.status for failure in query_failures}
    status_summary = ", ".join(sorted(failed_statuses))
    return (
        f"{display_name} {channel_label} returned {status_summary} for "
        f"{len(query_failures)} query and retained results from "
        f"{completed_query_count} completed queries."
    )


def _format_retry_after(retry_after_seconds: int | None) -> str:
    if retry_after_seconds is None:
        return "Please try again later."

    minutes, seconds = divmod(retry_after_seconds, 60)
    if minutes == 0:
        unit = "second" if seconds == 1 else "seconds"
        return f"Try again in {seconds} {unit}."
    if seconds == 0:
        unit = "minute" if minutes == 1 else "minutes"
        return f"Try again in {minutes} {unit}."

    minute_unit = "minute" if minutes == 1 else "minutes"
    second_unit = "second" if seconds == 1 else "seconds"
    return f"Try again in {minutes} {minute_unit} {seconds} {second_unit}."


def summarize_queries(queries: Sequence[str], *, max_items: int = 5) -> str:
    """Return one compact query summary for logs."""

    visible_queries = [query.strip() for query in queries if query.strip()][:max_items]
    suffix = ""
    if len(queries) > max_items:
        suffix = f" ... (+{len(queries) - max_items} more)"
    return ", ".join(repr(query) for query in visible_queries) + suffix

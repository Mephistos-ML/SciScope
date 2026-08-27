"""Source discovery orchestration for external retrieval."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from queue import Empty, Queue
from urllib.parse import urlparse

from app.config import GITLAB_BASE_URL
from app.services.search.observability import SearchLogContext, log_search_event
from app.services.search.retrieval.lanes import (
    LaneResult,
    RepositoryDiscoverer,
    RetrievalProgressCallback,
    consume_lane_result,
    emit_retrieval_progress,
    start_lane_worker,
)
from app.services.search.retrieval.timeouts import (
    build_deadline_warning,
    build_lane_deadline_monotonic,
    read_wait_timeout_seconds,
)
from app.sources.github.search import (
    discover_repository_candidates as discover_github_repository_candidates,
)
from app.sources.github.search import (
    discover_repository_candidates_from_code as discover_github_repository_candidates_from_code,
)
from app.sources.gitlab.search import (
    discover_repository_candidates as discover_gitlab_repository_candidates,
)
from app.sources.gitlab.search import (
    discover_repository_candidates_from_code as discover_gitlab_repository_candidates_from_code,
)

logger = logging.getLogger(__name__)

SourceRetriever = tuple[str, str, RepositoryDiscoverer]
ActiveSourceRetriever = tuple[str, str, RepositoryDiscoverer, bool]


def discover_candidates_across_sources(
    queries: Sequence[str],
    *,
    discoverers: Sequence[SourceRetriever] | None = None,
    progress_callback: RetrievalProgressCallback | None = None,
    soft_deadline_monotonic: float | None = None,
    hard_deadline_monotonic: float | None = None,
    log_context: SearchLogContext | None = None,
) -> dict[str, object]:
    """Discover repository candidates across all active retrieval lanes."""

    candidates = []
    source_statuses_by_source: dict[str, dict[str, object]] = {}
    successful_sources: set[str] = set()
    warnings: list[str] = []
    partial = False

    active_discoverers = build_active_discoverers(discoverers)
    if (
        discoverers is None
        and not supports_gitlab_global_code_search()
        and log_context is not None
    ):
        log_search_event(
            logger=logger,
            event="explore_retrieval_lane_failed",
            context=log_context,
            level=logging.INFO,
            duration_ms=0,
            source="gitlab",
            channel="code_search",
            status="disabled",
            query_count=len(queries),
            candidate_count=0,
            error_code="unsupported_search_capability",
            error_message="GitLab global code search is unsupported for this base URL.",
        )

    lane_results: Queue[LaneResult] = Queue()
    for (
        source_name,
        channel_name,
        discover_candidates,
        supports_deadline,
    ) in active_discoverers:
        start_lane_worker(
            source_name=source_name,
            channel_name=channel_name,
            discover_candidates=discover_candidates,
            supports_deadline=supports_deadline,
            queries=queries,
            deadline_monotonic=build_lane_deadline_monotonic(
                channel_name=channel_name,
                soft_deadline_monotonic=soft_deadline_monotonic,
                hard_deadline_monotonic=hard_deadline_monotonic,
            ),
            result_queue=lane_results,
        )

    remaining_lane_count = len(active_discoverers)
    while remaining_lane_count > 0:
        wait_timeout_seconds = read_wait_timeout_seconds(
            soft_deadline_monotonic=soft_deadline_monotonic,
            hard_deadline_monotonic=hard_deadline_monotonic,
        )
        try:
            lane_result = (
                lane_results.get(
                    timeout=wait_timeout_seconds,
                )
                if wait_timeout_seconds is not None
                else lane_results.get()
            )
        except Empty:
            partial = True
            warning, log_level = build_deadline_warning(
                soft_deadline_monotonic=soft_deadline_monotonic,
                hard_deadline_monotonic=hard_deadline_monotonic,
            )
            warnings.append(warning)
            logger.log(log_level, warning)
            break

        remaining_lane_count -= 1
        lane_partial, lane_warning = consume_lane_result(
            lane_result,
            queries=queries,
            candidates=candidates,
            source_statuses_by_source=source_statuses_by_source,
            successful_sources=successful_sources,
            log_context=log_context,
        )
        if lane_partial:
            partial = True
        if lane_warning is not None:
            warnings.append(lane_warning)
        emit_retrieval_progress(
            candidates,
            source_statuses_by_source,
            successful_sources,
            progress_callback,
            partial=partial,
            warnings=warnings,
        )

    source_statuses = list(source_statuses_by_source.values())
    if partial and not source_statuses and warnings:
        source_statuses = [
            {
                "source": "system",
                "status": "timed_out",
                "candidateCount": 0,
                "error": warnings[0],
            }
        ]

    return {
        "candidates": candidates,
        "source_statuses": source_statuses,
        "successful_source_count": len(successful_sources),
        "partial": partial,
        "warnings": warnings,
    }


def build_active_discoverers(
    discoverers: Sequence[SourceRetriever] | None,
) -> tuple[ActiveSourceRetriever, ...]:
    """Build the active retrieval lanes for one search."""

    if discoverers is None:
        return tuple(
            (source_name, channel_name, discoverer, True)
            for source_name, channel_name, discoverer in build_default_discoverers()
        )
    return tuple(
        (source_name, channel_name, discoverer, False)
        for source_name, channel_name, discoverer in discoverers
    )


def build_default_discoverers() -> tuple[SourceRetriever, ...]:
    """Build the default source retriever list."""

    discoverers: list[SourceRetriever] = [
        ("github", "repository_search", discover_github_repository_candidates),
        ("github", "code_search", discover_github_repository_candidates_from_code),
        ("gitlab", "repository_search", discover_gitlab_repository_candidates),
    ]

    if supports_gitlab_global_code_search():
        discoverers.append(
            ("gitlab", "code_search", discover_gitlab_repository_candidates_from_code)
        )
    else:
        logger.info(
            "Skipping gitlab code_search lane for base_url=%s because gitlab.com global blob search is unsupported.",
            GITLAB_BASE_URL,
        )

    return tuple(discoverers)


def supports_gitlab_global_code_search() -> bool:
    """Return whether the configured GitLab base URL supports global blob search."""

    hostname = (urlparse(GITLAB_BASE_URL).hostname or "").casefold()
    return hostname not in {"gitlab.com", "www.gitlab.com"}

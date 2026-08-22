"""External repository retrieval orchestration for Explore."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from time import monotonic
from typing import Callable
from urllib.parse import urlparse

from app.config import (
    EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS,
    EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS,
    GITLAB_BASE_URL,
)
from app.models.signal import Signal
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval.models import RetrievedCandidates, RetrievalHit
from app.sources.common import RepositorySourceError, build_source_status
from app.sources.github.search import (
    discover_repository_candidates as discover_github_repository_candidates,
    discover_repository_candidates_from_code as discover_github_repository_candidates_from_code,
)
from app.sources.gitlab.search import (
    discover_repository_candidates as discover_gitlab_repository_candidates,
    discover_repository_candidates_from_code as discover_gitlab_repository_candidates_from_code,
)

logger = logging.getLogger(__name__)

RepositoryDiscoverer = Callable[[Sequence[str]], list[Signal]]
SourceRetriever = tuple[str, str, RepositoryDiscoverer]
ActiveSourceRetriever = tuple[str, str, RepositoryDiscoverer, bool]
RetrievalProgressCallback = Callable[[RetrievedCandidates], None]

SOURCE_DISPLAY_NAMES = {
    "github": "GitHub",
    "gitlab": "GitLab",
}


def run_external_repository_retrieval(
    queries: Sequence[str],
    *,
    discoverers: Sequence[SourceRetriever] | None = None,
    progress_callback: RetrievalProgressCallback | None = None,
    soft_deadline_monotonic: float | None = None,
    hard_deadline_monotonic: float | None = None,
) -> RetrievedCandidates:
    """Retrieve and deduplicate repository candidates across active sources."""

    retrieval_state = _discover_candidates_across_sources(
        queries,
        discoverers=discoverers,
        progress_callback=progress_callback,
        soft_deadline_monotonic=soft_deadline_monotonic,
        hard_deadline_monotonic=hard_deadline_monotonic,
    )
    return RetrievedCandidates(
        candidates=merge_retrieval_hits(tuple(retrieval_state["candidates"])),
        source_statuses=tuple(retrieval_state["source_statuses"]),
        successful_source_count=int(retrieval_state["successful_source_count"]),
        partial=bool(retrieval_state["partial"]),
        warnings=tuple(str(warning) for warning in retrieval_state["warnings"]),
    )


def _discover_candidates_across_sources(
    queries: Sequence[str],
    *,
    discoverers: Sequence[SourceRetriever] | None = None,
    progress_callback: RetrievalProgressCallback | None = None,
    soft_deadline_monotonic: float | None = None,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, object]:
    candidates: list[RetrievalHit] = []
    source_statuses_by_source: dict[str, dict[str, object]] = {}
    successful_sources: set[str] = set()
    warnings: list[str] = []
    partial = False

    active_discoverers = _build_active_discoverers(discoverers)

    for source_name, channel_name, discover_candidates, supports_deadline in active_discoverers:
        if _is_deadline_reached(soft_deadline_monotonic):
            partial = True
            warnings.append(
                "Search completed with partial coverage because the time budget expired before all lanes finished."
            )
            logger.info(
                "Explore retrieval stopped before source=%s channel=%s because the soft deadline expired.",
                source_name,
                channel_name,
            )
            break

        if _is_deadline_reached(hard_deadline_monotonic):
            partial = True
            warnings.append(
                "Search completed with partial coverage because the hard timeout was reached."
            )
            logger.warning(
                "Explore retrieval stopped before source=%s channel=%s because the hard deadline expired.",
                source_name,
                channel_name,
            )
            break

        logger.info(
            "Explore retrieval started for source=%s channel=%s query_count=%s queries=%s",
            source_name,
            channel_name,
            len(queries),
            _summarize_queries(queries),
        )
        lane_deadline_monotonic = _build_lane_deadline_monotonic(
            channel_name=channel_name,
            hard_deadline_monotonic=hard_deadline_monotonic,
        )
        try:
            source_candidates = _run_discoverer(
                discover_candidates,
                queries,
                lane_deadline_monotonic=lane_deadline_monotonic,
                supports_deadline=supports_deadline,
            )
        except RepositorySourceError as exc:
            partial = True
            warnings.append(
                f"{SOURCE_DISPLAY_NAMES[source_name]} {channel_name.replace('_', ' ')} returned {exc.status}."
            )
            logger.warning(
                (
                    "Explore retrieval failed for source=%s channel=%s status=%s "
                    "queries=%s message=%s"
                ),
                source_name,
                channel_name,
                exc.status,
                _summarize_queries(queries),
                exc.public_message,
            )
            _merge_source_status(
                source_statuses_by_source,
                build_source_status(
                    source=source_name,
                    status=exc.status,
                    candidate_count=0,
                    error=exc.public_message,
                ),
            )
            _emit_retrieval_progress(
                candidates,
                source_statuses_by_source,
                successful_sources,
                progress_callback,
                partial=partial,
                warnings=warnings,
            )
            continue
        except Exception:
            partial = True
            warnings.append(
                f"{SOURCE_DISPLAY_NAMES[source_name]} {channel_name.replace('_', ' ')} crashed."
            )
            logger.exception(
                "Explore retrieval crashed for source=%s channel=%s queries=%s",
                source_name,
                channel_name,
                _summarize_queries(queries),
            )
            _merge_source_status(
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
            _emit_retrieval_progress(
                candidates,
                source_statuses_by_source,
                successful_sources,
                progress_callback,
                partial=partial,
                warnings=warnings,
            )
            continue

        logger.info(
            "Explore retrieval completed for source=%s channel=%s candidate_count=%s",
            source_name,
            channel_name,
            len(source_candidates),
        )
        successful_sources.add(source_name)
        candidates.extend(
            RetrievalHit(
                source=source_name,
                channel=channel_name,
                query=str(signal.payload.get("query") or ""),
                rank=index,
                signal=signal,
            )
            for index, signal in enumerate(source_candidates, start=1)
        )
        _merge_source_status(
            source_statuses_by_source,
            build_source_status(
                source=source_name,
                status="ok",
                candidate_count=len(source_candidates),
                error=None,
            ),
        )
        _emit_retrieval_progress(
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


def _build_active_discoverers(
    discoverers: Sequence[SourceRetriever] | None,
) -> tuple[ActiveSourceRetriever, ...]:
    if discoverers is None:
        return tuple(
            (source_name, channel_name, discoverer, True)
            for source_name, channel_name, discoverer in _build_default_discoverers()
        )
    return tuple(
        (source_name, channel_name, discoverer, False)
        for source_name, channel_name, discoverer in discoverers
    )


def _build_default_discoverers() -> tuple[SourceRetriever, ...]:
    discoverers: list[SourceRetriever] = [
        ("github", "repository_search", discover_github_repository_candidates),
        ("github", "code_search", discover_github_repository_candidates_from_code),
        ("gitlab", "repository_search", discover_gitlab_repository_candidates),
    ]

    if _supports_gitlab_global_code_search():
        discoverers.append(
            ("gitlab", "code_search", discover_gitlab_repository_candidates_from_code)
        )
    else:
        logger.info(
            "Skipping gitlab code_search lane for base_url=%s because gitlab.com global blob search is unsupported.",
            GITLAB_BASE_URL,
        )

    return tuple(discoverers)


def _supports_gitlab_global_code_search() -> bool:
    hostname = (urlparse(GITLAB_BASE_URL).hostname or "").casefold()
    return hostname not in {"gitlab.com", "www.gitlab.com"}


def _build_lane_deadline_monotonic(
    *,
    channel_name: str,
    hard_deadline_monotonic: float | None,
) -> float | None:
    lane_budget_seconds = (
        EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS
        if channel_name == "code_search"
        else EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS
    )
    lane_deadline_monotonic = monotonic() + lane_budget_seconds
    if hard_deadline_monotonic is None:
        return lane_deadline_monotonic
    return min(lane_deadline_monotonic, hard_deadline_monotonic)


def _run_discoverer(
    discover_candidates: RepositoryDiscoverer,
    queries: Sequence[str],
    *,
    lane_deadline_monotonic: float | None,
    supports_deadline: bool,
) -> list[Signal]:
    if not supports_deadline:
        return list(discover_candidates(queries))
    return list(
        discover_candidates(
            queries,
            deadline_monotonic=lane_deadline_monotonic,
        )
    )


def _is_deadline_reached(deadline_monotonic: float | None) -> bool:
    return deadline_monotonic is not None and monotonic() >= deadline_monotonic


def _summarize_queries(queries: Sequence[str], *, max_items: int = 5) -> str:
    visible_queries = [query.strip() for query in queries if query.strip()][:max_items]
    suffix = ""
    if len(queries) > max_items:
        suffix = f" ... (+{len(queries) - max_items} more)"
    return ", ".join(repr(query) for query in visible_queries) + suffix


def _merge_source_status(
    statuses_by_source: dict[str, dict[str, object]],
    incoming: dict[str, object],
) -> None:
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


def _emit_retrieval_progress(
    candidates: list[RetrievalHit],
    source_statuses_by_source: dict[str, dict[str, object]],
    successful_sources: set[str],
    progress_callback: RetrievalProgressCallback | None,
    *,
    partial: bool,
    warnings: list[str],
) -> None:
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

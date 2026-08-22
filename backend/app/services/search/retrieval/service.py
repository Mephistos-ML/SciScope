"""External repository retrieval orchestration for Explore."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Callable

from app.models.signal import Signal
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval.models import RetrievedCandidates, RetrievalHit
from app.sources.common import RepositorySourceError, build_source_status
from app.sources.github.search import (
    discover_repository_candidates as discover_github_repository_candidates,
    discover_repository_candidates_from_readme as discover_github_repository_candidates_from_readme,
)
from app.sources.gitlab.search import (
    discover_repository_candidates as discover_gitlab_repository_candidates,
    discover_repository_candidates_from_readme as discover_gitlab_repository_candidates_from_readme,
)

logger = logging.getLogger(__name__)

RepositoryDiscoverer = Callable[[Sequence[str]], list[Signal]]
SourceRetriever = tuple[str, str, RepositoryDiscoverer]

SOURCE_DISPLAY_NAMES = {
    "github": "GitHub",
    "gitlab": "GitLab",
}


def run_external_repository_retrieval(
    queries: Sequence[str],
    *,
    discoverers: Sequence[SourceRetriever] | None = None,
) -> RetrievedCandidates:
    """Retrieve and deduplicate repository candidates across active sources."""

    candidates, source_statuses, successful_sources = _discover_candidates_across_sources(
        queries,
        discoverers=discoverers,
    )
    return RetrievedCandidates(
        candidates=merge_retrieval_hits(tuple(candidates)),
        source_statuses=tuple(source_statuses),
        successful_source_count=successful_sources,
    )


def _discover_candidates_across_sources(
    queries: Sequence[str],
    *,
    discoverers: Sequence[SourceRetriever] | None = None,
) -> tuple[list[RetrievalHit], list[dict[str, object]], int]:
    candidates: list[RetrievalHit] = []
    source_statuses_by_source: dict[str, dict[str, object]] = {}
    successful_sources: set[str] = set()

    active_discoverers = discoverers or (
        ("github", "repository_search", discover_github_repository_candidates),
        ("github", "readme_search", discover_github_repository_candidates_from_readme),
        ("gitlab", "repository_search", discover_gitlab_repository_candidates),
        ("gitlab", "readme_search", discover_gitlab_repository_candidates_from_readme),
    )

    for source_name, channel_name, discover_candidates in active_discoverers:
        try:
            source_candidates = list(discover_candidates(queries))
        except RepositorySourceError as exc:
            logger.warning(
                "Repository source %s is unavailable for explore search: %s",
                source_name,
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
            continue
        except Exception:
            logger.exception(
                "Repository source %s failed during explore search.",
                source_name,
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
            continue

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

    return candidates, list(source_statuses_by_source.values()), len(successful_sources)


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

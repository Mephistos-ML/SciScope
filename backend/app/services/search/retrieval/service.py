"""External repository retrieval orchestration for Explore."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Callable

from app.models.signal import Signal
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval.models import RetrievedCandidates, RetrievalHit
from app.sources.common import RepositorySourceError, build_source_status
from app.sources.github.discovery import (
    discover_repository_candidates as discover_github_repository_candidates,
)
from app.sources.gitlab.discovery import (
    discover_repository_candidates as discover_gitlab_repository_candidates,
)

logger = logging.getLogger(__name__)

RepositoryDiscoverer = Callable[[Sequence[str]], list[Signal]]

SOURCE_DISPLAY_NAMES = {
    "github": "GitHub",
    "gitlab": "GitLab",
}


def run_external_repository_retrieval(
    queries: Sequence[str],
    *,
    discoverers: Sequence[tuple[str, RepositoryDiscoverer]] | None = None,
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
    discoverers: Sequence[tuple[str, RepositoryDiscoverer]] | None = None,
) -> tuple[list[RetrievalHit], list[dict[str, object]], int]:
    candidates: list[RetrievalHit] = []
    source_statuses: list[dict[str, object]] = []
    successful_sources = 0

    active_discoverers = discoverers or (
        ("github", discover_github_repository_candidates),
        ("gitlab", discover_gitlab_repository_candidates),
    )

    for source_name, discover_candidates in active_discoverers:
        try:
            source_candidates = list(discover_candidates(queries))
        except RepositorySourceError as exc:
            logger.warning(
                "Repository source %s is unavailable for explore search: %s",
                source_name,
                exc.public_message,
            )
            source_statuses.append(
                build_source_status(
                    source=source_name,
                    status=exc.status,
                    candidate_count=0,
                    error=exc.public_message,
                )
            )
            continue
        except Exception:
            logger.exception(
                "Repository source %s failed during explore search.",
                source_name,
            )
            source_statuses.append(
                build_source_status(
                    source=source_name,
                    status="error",
                    candidate_count=0,
                    error=(
                        f"{SOURCE_DISPLAY_NAMES[source_name]} repository search is "
                        "unavailable right now."
                    ),
                )
            )
            continue

        successful_sources += 1
        candidates.extend(
            RetrievalHit(
                source=source_name,
                channel="repository_search",
                query=str(signal.payload.get("query") or ""),
                rank=index,
                signal=signal,
            )
            for index, signal in enumerate(source_candidates, start=1)
        )
        source_statuses.append(
            build_source_status(
                source=source_name,
                status="ok",
                candidate_count=len(source_candidates),
                error=None,
            )
        )

    return candidates, source_statuses, successful_sources

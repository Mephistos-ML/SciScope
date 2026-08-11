"""Repository-family orchestration across concrete source adapters."""

from __future__ import annotations

import logging

from app.config import DATABASE_URL
from app.models.discovery import DiscoveryResult
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile
from app.sources.repositories.common import RepositorySourceError
from app.sources.repositories.github.discovery import discover_github_entities_for_profile
from app.sources.repositories.github.monitor import load_github_signals_for_profile
from app.sources.repositories.github.state import (
    describe_release_checkpoints as describe_github_release_checkpoints,
    describe_watched_github_repositories,
    sync_github_baseline_for_profile,
)
from app.sources.repositories.gitlab.discovery import discover_gitlab_entities_for_profile
from app.sources.repositories.gitlab.monitor import load_gitlab_signals_for_profile
from app.sources.repositories.gitlab.state import (
    describe_release_checkpoints as describe_gitlab_release_checkpoints,
    describe_watched_gitlab_repositories,
    sync_gitlab_baseline_for_profile,
)

logger = logging.getLogger(__name__)


def discover_repository_entities_for_profile(
    profile: ResearchProfile,
    *,
    database_url: str | None = None,
) -> DiscoveryResult:
    """Discover repository entities across all configured repository sources."""

    resolved_database_url = database_url or DATABASE_URL
    results: list[DiscoveryResult] = []

    for source_name, discover_entities in (
        ("github", discover_github_entities_for_profile),
        ("gitlab", discover_gitlab_entities_for_profile),
    ):
        try:
            results.append(
                discover_entities(profile, database_url=resolved_database_url)
            )
        except RepositorySourceError as exc:
            logger.warning(
                "Repository discovery source %s skipped: %s",
                source_name,
                exc.public_message,
            )
        except Exception:
            logger.exception(
                "Repository discovery source %s failed unexpectedly.",
                source_name,
            )

    if not results:
        raise RuntimeError(
            "Repository discovery is unavailable because every repository source failed."
        )

    merged_queries: list[str] = []
    seen_queries: set[str] = set()
    for result in results:
        for query in result.queries:
            if query in seen_queries:
                continue
            seen_queries.add(query)
            merged_queries.append(query)

    return DiscoveryResult(
        topic_slug=profile.topic_slug,
        queries=tuple(merged_queries),
        candidate_count=sum(result.candidate_count for result in results),
        entity_count=sum(result.entity_count for result in results),
        matched_entity_count=sum(result.matched_entity_count for result in results),
    )


def sync_repository_baseline_for_profile(profile: ResearchProfile) -> None:
    """Initialize monitoring baselines across repository sources."""

    for source_name, sync_baseline in (
        ("github", sync_github_baseline_for_profile),
        ("gitlab", sync_gitlab_baseline_for_profile),
    ):
        try:
            sync_baseline(profile)
        except RepositorySourceError as exc:
            logger.warning(
                "Repository baseline sync skipped for %s: %s",
                source_name,
                exc.public_message,
            )
        except Exception:
            logger.exception(
                "Repository baseline sync failed for %s.",
                source_name,
            )


def load_repository_signals_for_profile(profile: ResearchProfile) -> list[RawSignal]:
    """Load live repository release signals across repository sources."""

    signals: list[RawSignal] = []
    for source_name, load_signals in (
        ("github", load_github_signals_for_profile),
        ("gitlab", load_gitlab_signals_for_profile),
    ):
        try:
            signals.extend(load_signals(profile))
        except RepositorySourceError as exc:
            logger.warning(
                "Repository monitoring source %s skipped: %s",
                source_name,
                exc.public_message,
            )
        except Exception:
            logger.exception(
                "Repository monitoring source %s failed unexpectedly.",
                source_name,
            )

    return signals


def describe_watched_repositories(subscription_id: str) -> list[dict[str, object]]:
    """Return watched repository debug metadata across repository sources."""

    return [
        *describe_watched_github_repositories(subscription_id),
        *describe_watched_gitlab_repositories(subscription_id),
    ]


def describe_repository_checkpoints(subscription_id: str) -> list[dict[str, object]]:
    """Return repository checkpoint debug metadata across repository sources."""

    return [
        *describe_github_release_checkpoints(subscription_id),
        *describe_gitlab_release_checkpoints(subscription_id),
    ]

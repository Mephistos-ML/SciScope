"""Repository-family orchestration across concrete source adapters."""

from __future__ import annotations

from pathlib import Path

from app.models.discovery import DiscoveryResult
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile
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
from app.storage.seen_signals import DB_PATH


def discover_repository_entities_for_profile(
    profile: ResearchProfile,
    *,
    db_path: Path = DB_PATH,
) -> DiscoveryResult:
    """Discover repository entities across all configured repository sources."""

    results = [
        discover_github_entities_for_profile(profile, db_path=db_path),
        discover_gitlab_entities_for_profile(profile, db_path=db_path),
    ]

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

    sync_github_baseline_for_profile(profile)
    sync_gitlab_baseline_for_profile(profile)


def load_repository_signals_for_profile(profile: ResearchProfile) -> list[RawSignal]:
    """Load live repository release signals across repository sources."""

    return [
        *load_github_signals_for_profile(profile),
        *load_gitlab_signals_for_profile(profile),
    ]


def describe_watched_repositories(topic_slug: str) -> list[dict[str, object]]:
    """Return watched repository debug metadata across repository sources."""

    return [
        *describe_watched_github_repositories(topic_slug),
        *describe_watched_gitlab_repositories(topic_slug),
    ]


def describe_repository_checkpoints(topic_slug: str) -> list[dict[str, object]]:
    """Return repository checkpoint debug metadata across repository sources."""

    return [
        *describe_github_release_checkpoints(topic_slug),
        *describe_gitlab_release_checkpoints(topic_slug),
    ]

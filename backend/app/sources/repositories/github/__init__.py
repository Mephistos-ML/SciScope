"""GitHub repository source namespace."""

from app.sources.repositories.github.auth import build_auth_headers
from app.sources.repositories.github.discovery import (
    discover_github_entities_for_profile,
    discover_repository_candidates,
)
from app.sources.repositories.github.monitor import (
    load_github_signals_for_profile,
    load_repo_activity,
)
from app.sources.repositories.common.query_builder import build_repository_search_queries
from app.sources.repositories.github.state import (
    describe_release_checkpoints,
    describe_watched_github_repositories,
    sync_github_baseline_for_profile,
)

__all__ = [
    "build_auth_headers",
    "build_repository_search_queries",
    "describe_release_checkpoints",
    "describe_watched_github_repositories",
    "discover_github_entities_for_profile",
    "discover_repository_candidates",
    "load_github_signals_for_profile",
    "load_repo_activity",
    "sync_github_baseline_for_profile",
]

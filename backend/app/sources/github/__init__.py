"""GitHub source namespace."""

from app.sources.github.discovery import discover_repository_candidates
from app.sources.github.monitor import load_github_signals_for_profile, load_repo_activity
from app.sources.github.query_builder import build_repository_search_queries
from app.sources.github.state import (
    describe_release_checkpoints,
    describe_watched_github_repositories,
    sync_github_baseline_for_profile,
)

__all__ = [
    "build_repository_search_queries",
    "describe_release_checkpoints",
    "describe_watched_github_repositories",
    "discover_repository_candidates",
    "load_github_signals_for_profile",
    "load_repo_activity",
    "sync_github_baseline_for_profile",
]

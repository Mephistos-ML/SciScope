"""GitHub repository source namespace."""

from app.sources.github.auth import build_auth_headers
from app.sources.github.discovery import (
    discover_github_repositories_for_profile,
    discover_repository_candidates,
)
from app.sources.github.monitor import (
    load_github_signals_for_profile,
    load_repo_activity,
)
from app.sources.github.state import (
    describe_release_checkpoints,
    describe_watched_github_repositories,
    sync_github_baseline_for_profile,
)

__all__ = [
    "build_auth_headers",
    "describe_release_checkpoints",
    "describe_watched_github_repositories",
    "discover_github_repositories_for_profile",
    "discover_repository_candidates",
    "load_github_signals_for_profile",
    "load_repo_activity",
    "sync_github_baseline_for_profile",
]

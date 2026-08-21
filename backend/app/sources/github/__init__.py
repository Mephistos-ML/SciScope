"""GitHub repository source namespace."""

from app.sources.github.auth import build_auth_headers
from app.sources.github.search import (
    discover_repository_candidates,
    discover_repository_candidates_from_readme,
)
from app.sources.github.monitor import load_github_signals_for_subscription, load_repo_activity
from app.sources.github.state import resolve_release_checkpoint, sync_github_baseline

__all__ = [
    "build_auth_headers",
    "discover_repository_candidates",
    "discover_repository_candidates_from_readme",
    "load_github_signals_for_subscription",
    "load_repo_activity",
    "resolve_release_checkpoint",
    "sync_github_baseline",
]

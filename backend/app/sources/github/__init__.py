"""GitHub repository source namespace."""

from app.sources.github.auth import build_auth_headers
from app.sources.github.search import (
    discover_repository_candidates,
    discover_repository_candidates_from_readme,
)
from app.sources.github.monitor import load_repo_activity

__all__ = [
    "build_auth_headers",
    "discover_repository_candidates",
    "discover_repository_candidates_from_readme",
    "load_repo_activity",
]

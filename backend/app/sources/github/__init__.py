"""GitHub repository source namespace."""

from app.sources.github.auth import build_auth_headers
from app.sources.github.search.code import discover_repository_candidates_from_code
from app.sources.github.search.repository import discover_repository_candidates
from app.sources.github.monitor import (
    load_repository_activity,
    refresh_repository_profile,
)

__all__ = [
    "build_auth_headers",
    "discover_repository_candidates",
    "discover_repository_candidates_from_code",
    "load_repository_activity",
    "refresh_repository_profile",
]

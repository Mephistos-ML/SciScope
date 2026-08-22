"""GitVerse repository source placeholder namespace."""

from app.sources.gitverse.auth import build_auth_headers
from app.sources.gitverse.client import (
    GITVERSE_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.sources.gitverse.discovery import discover_repository_candidates
from app.sources.gitverse.monitor import load_repo_activity

__all__ = [
    "GITVERSE_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "discover_repository_candidates",
    "fetch_json",
    "load_repo_activity",
]

"""GitCode repository source placeholder namespace."""

from app.sources.gitcode.auth import build_auth_headers
from app.sources.gitcode.client import (
    GITCODE_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.sources.gitcode.discovery import discover_repository_candidates
from app.sources.gitcode.monitor import load_repo_activity

__all__ = [
    "GITCODE_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "discover_repository_candidates",
    "fetch_json",
    "load_repo_activity",
]

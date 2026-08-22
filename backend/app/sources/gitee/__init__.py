"""Gitee repository source placeholder namespace."""

from app.sources.gitee.auth import build_auth_headers
from app.sources.gitee.client import (
    GITEE_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.sources.gitee.discovery import discover_repository_candidates
from app.sources.gitee.monitor import load_repo_activity

__all__ = [
    "GITEE_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "discover_repository_candidates",
    "fetch_json",
    "load_repo_activity",
]

"""Gitee repository source placeholder namespace."""

from app.sources.gitee.auth import build_auth_headers
from app.sources.gitee.client import (
    GITEE_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.sources.gitee.discovery import (
    discover_gitee_entities_for_profile,
    discover_repository_candidates,
)
from app.sources.gitee.monitor import (
    load_gitee_signals_for_profile,
    load_repo_activity,
)
from app.sources.gitee.state import (
    describe_release_checkpoints,
    describe_watched_gitee_repositories,
    sync_gitee_baseline_for_profile,
)

__all__ = [
    "GITEE_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "describe_release_checkpoints",
    "describe_watched_gitee_repositories",
    "discover_gitee_entities_for_profile",
    "discover_repository_candidates",
    "fetch_json",
    "load_gitee_signals_for_profile",
    "load_repo_activity",
    "sync_gitee_baseline_for_profile",
]

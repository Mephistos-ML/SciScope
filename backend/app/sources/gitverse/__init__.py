"""GitVerse repository source placeholder namespace."""

from app.sources.gitverse.auth import build_auth_headers
from app.sources.gitverse.client import (
    GITVERSE_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.sources.gitverse.discovery import discover_repository_candidates
from app.sources.gitverse.monitor import (
    load_gitverse_signals_for_subscription,
    load_repo_activity,
)
from app.sources.gitverse.state import (
    describe_release_checkpoints,
    resolve_release_checkpoint,
    sync_gitverse_baseline,
)

__all__ = [
    "GITVERSE_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "describe_release_checkpoints",
    "discover_repository_candidates",
    "fetch_json",
    "load_gitverse_signals_for_subscription",
    "load_repo_activity",
    "resolve_release_checkpoint",
    "sync_gitverse_baseline",
]

"""GitVerse repository source placeholder namespace."""

from app.sources.repositories.gitverse.auth import build_auth_headers
from app.sources.repositories.gitverse.client import (
    GITVERSE_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.sources.repositories.gitverse.discovery import (
    discover_gitverse_entities_for_profile,
    discover_repository_candidates,
)
from app.sources.repositories.gitverse.monitor import (
    load_gitverse_signals_for_profile,
    load_repo_activity,
)
from app.sources.repositories.gitverse.state import (
    describe_release_checkpoints,
    describe_watched_gitverse_repositories,
    sync_gitverse_baseline_for_profile,
)

__all__ = [
    "GITVERSE_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "describe_release_checkpoints",
    "describe_watched_gitverse_repositories",
    "discover_gitverse_entities_for_profile",
    "discover_repository_candidates",
    "fetch_json",
    "load_gitverse_signals_for_profile",
    "load_repo_activity",
    "sync_gitverse_baseline_for_profile",
]

"""GitLab repository source family."""

from app.integrations.repositories.gitlab.auth import build_auth_headers
from app.integrations.repositories.gitlab.client import (
    GITLAB_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.integrations.repositories.gitlab.search.code import discover_repository_candidates_from_code
from app.integrations.repositories.gitlab.search.repository import discover_repository_candidates
from app.integrations.repositories.gitlab.monitor import (
    load_repository_activity,
    refresh_repository_profile,
)

__all__ = [
    "GITLAB_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "discover_repository_candidates",
    "discover_repository_candidates_from_code",
    "fetch_json",
    "load_repository_activity",
    "refresh_repository_profile",
]

"""GitLab repository source family."""

from app.sources.gitlab.auth import build_auth_headers
from app.sources.gitlab.client import (
    GITLAB_API_BASE,
    build_user_agent,
    fetch_json,
)
from app.sources.gitlab.search import (
    discover_repository_candidates,
    discover_repository_candidates_from_readme,
)

__all__ = [
    "GITLAB_API_BASE",
    "build_auth_headers",
    "build_user_agent",
    "discover_repository_candidates",
    "discover_repository_candidates_from_readme",
    "fetch_json",
]

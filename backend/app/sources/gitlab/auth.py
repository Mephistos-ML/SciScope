"""Authentication helpers for GitLab API requests."""

from __future__ import annotations

from app.config import GITLAB_AUTH_MODE, GITLAB_SERVICE_ACCOUNT_TOKEN
from app.sources.common import RepositorySourceError


def build_auth_headers() -> dict[str, str]:
    """Build required authentication headers for GitLab API requests."""

    if GITLAB_AUTH_MODE == "disabled":
        raise RepositorySourceError(
            source="gitlab",
            status="disabled",
            public_message="GitLab repository search is disabled in this environment.",
        )

    if GITLAB_AUTH_MODE != "service_account":
        raise RepositorySourceError(
            source="gitlab",
            status="misconfigured",
            public_message=(
                "GitLab repository search is misconfigured. Expected "
                "GITLAB_AUTH_MODE=service_account or disabled."
            ),
        )

    token = GITLAB_SERVICE_ACCOUNT_TOKEN
    if not token:
        raise RepositorySourceError(
            source="gitlab",
            status="misconfigured",
            public_message=(
                "GitLab repository search is misconfigured. Missing "
                "GITLAB_SERVICE_ACCOUNT_TOKEN."
            ),
        )

    return {"PRIVATE-TOKEN": token}

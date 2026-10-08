"""Authentication helpers for GitLab API requests."""

from __future__ import annotations

from app.integrations.repositories.common.source_status import RepositorySourceError


def build_auth_headers(*, mode: str, token: str) -> dict[str, str]:
    """Build required authentication headers for GitLab API requests."""

    if mode == "disabled":
        raise RepositorySourceError(
            source="gitlab",
            status="disabled",
            public_message="GitLab repository search is disabled in this environment.",
        )

    if mode != "service_account":
        raise RepositorySourceError(
            source="gitlab",
            status="misconfigured",
            public_message=(
                "GitLab repository search is misconfigured. Expected "
                "GITLAB_AUTH_MODE=service_account or disabled."
            ),
        )

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

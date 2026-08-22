"""Repository builders for subscription application flows."""

from __future__ import annotations

from app.models.repository import Repository


def build_subscribed_repository(
    *,
    repository_item_id: str,
    repository_source: str,
    repository_full_name: str,
    repository_url: str,
    selected_query: str | None,
) -> Repository:
    """Build one repository entity from a direct subscription payload."""

    return Repository(
        repository_id=repository_item_id,
        source=repository_source,
        full_name=repository_full_name,
        url=repository_url,
        metadata={
            "repo": repository_full_name,
            "query": selected_query,
        },
    )

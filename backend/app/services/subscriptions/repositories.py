"""Repository builders for subscription application flows."""

from __future__ import annotations

from app.models.repository import Repository, parse_repository_id


def build_subscribed_repository(
    *,
    repository_item_id: str,
    repository_source: str,
    repository_full_name: str,
    repository_url: str,
    selected_query: str | None,
) -> Repository:
    """Build one canonical repository entity from a direct subscription payload."""

    provider_repository_id = parse_repository_id(
        repository_item_id,
        source=repository_source,
    )

    return Repository(
        repository_id=repository_item_id,
        source=repository_source,
        full_name=repository_full_name,
        url=repository_url,
        provider_repository_id=provider_repository_id,
        metadata={
            "repo": repository_full_name,
            "query": selected_query,
        },
    )

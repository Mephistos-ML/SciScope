"""GitHub repository search."""

from __future__ import annotations

from collections.abc import Sequence
from time import monotonic
from urllib.parse import quote_plus

from app.models.signal import Signal
from app.integrations.repositories.common.models import RepositoryCandidate
from app.integrations.repositories.common.factories import build_repository_candidate_signal
from app.integrations.repositories.common.deadlines import raise_source_timeout_error
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github.client import GitHubClient
from app.integrations.repositories.github.repository import map_repository_profile


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    client: GitHubClient,
    deadline_monotonic: float | None = None,
    per_query_limit: int = 50,
) -> list[Signal]:
    """Search GitHub repositories for topic-derived queries."""

    signals: list[Signal] = []
    for query in queries:
        if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
            raise_source_timeout_error(source="github", operation="repository search")
        search_url = _build_repository_search_url(
            query, per_query_limit=per_query_limit, client=client,
        )
        if deadline_monotonic is None:
            response = client.fetch_json(search_url)
        else:
            response = client.fetch_json(
                search_url,
                deadline_monotonic=deadline_monotonic,
            )
        payload = response.payload
        if not isinstance(payload, dict):
            continue

        items = payload.get("items")
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            full_name = str(item.get("full_name") or "").strip()
            provider_repository_id = str(item.get("id") or "").strip()
            if not full_name or not provider_repository_id:
                continue

            try:
                profile = map_repository_profile(item)
            except RepositorySourceError:
                continue

            candidate = RepositoryCandidate(
                source="github",
                full_name=profile.full_name,
                url=profile.url,
                query=query,
                provider_repository_id=profile.provider_repository_id,
                description=profile.description,
                owner_login=profile.owner_login,
                language=profile.language,
                stars=profile.stars,
                topics=profile.topics,
                provider_updated_at=profile.provider_updated_at,
            )
            signals.append(build_repository_candidate_signal(candidate))

    return signals


def _build_repository_search_url(query: str, *, client: GitHubClient, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{client.api_base}/search/repositories"
        f"?q={encoded_query}&sort=updated&order=desc&per_page={per_query_limit}"
    )

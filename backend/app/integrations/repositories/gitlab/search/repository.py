"""GitLab repository search."""

from __future__ import annotations

from collections.abc import Sequence
from time import monotonic
from urllib.parse import quote_plus

from app.models.signal import Signal
from app.integrations.repositories.common import (
    RepositoryCandidate,
    build_repository_candidate_signal,
    raise_source_timeout_error,
    RepositorySourceError,
)
from app.integrations.repositories.gitlab.client import GITLAB_API_BASE, fetch_json
from app.integrations.repositories.gitlab.repository import map_repository_profile


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    deadline_monotonic: float | None = None,
    per_query_limit: int = 30,
) -> list[Signal]:
    """Search GitLab projects for topic-derived queries."""

    signals: list[Signal] = []
    for query in queries:
        if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
            raise_source_timeout_error(source="gitlab", operation="repository search")
        search_url = _build_repository_search_url(query, per_query_limit=per_query_limit)
        if deadline_monotonic is None:
            response = fetch_json(search_url)
        else:
            response = fetch_json(
                search_url,
                deadline_monotonic=deadline_monotonic,
            )
        payload = response.payload
        if not isinstance(payload, list):
            continue

        for item in payload:
            if not isinstance(item, dict):
                continue

            full_name = str(item.get("path_with_namespace") or "").strip()
            provider_repository_id = str(item.get("id") or "").strip()
            if not full_name or not provider_repository_id:
                continue

            try:
                profile = map_repository_profile(item)
            except RepositorySourceError:
                continue

            candidate = RepositoryCandidate(
                source="gitlab",
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


def _build_repository_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITLAB_API_BASE}/search"
        f"?scope=projects&search={encoded_query}&per_page={per_query_limit}"
    )


def _dedupe_repository_candidates(
    candidates: list[Signal],
) -> dict[str, Signal]:
    deduped: dict[str, Signal] = {}
    for signal in candidates:
        existing = deduped.get(signal.item_id)
        if existing is None:
            deduped[signal.item_id] = signal
            continue

        existing_query = str(existing.payload.get("query") or "")
        incoming_query = str(signal.payload.get("query") or "")
        if len(incoming_query) > len(existing_query):
            deduped[signal.item_id] = signal

    return deduped

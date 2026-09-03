"""GitLab repository search."""

from __future__ import annotations

from collections.abc import Sequence
from time import monotonic
from urllib.parse import quote_plus

from app.models.repository import parse_provider_updated_at
from app.models.signal import Signal
from app.sources.common import (
    RepositoryCandidate,
    build_repository_candidate_signal,
    raise_source_timeout_error,
)
from app.sources.gitlab.client import GITLAB_API_BASE, fetch_json


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
            payload = fetch_json(search_url)
        else:
            payload = fetch_json(search_url, deadline_monotonic=deadline_monotonic)
        if not isinstance(payload, list):
            continue

        for item in payload:
            if not isinstance(item, dict):
                continue

            full_name = str(item.get("path_with_namespace") or "").strip()
            provider_repository_id = str(item.get("id") or "").strip()
            if not full_name or not provider_repository_id:
                continue

            description = str(item.get("description") or "")
            topics = item.get("topics")
            topic_list = [str(value) for value in topics] if isinstance(topics, list) else []
            stars = int(item.get("star_count") or 0)
            owner_login = full_name.split("/", 1)[0] if "/" in full_name else ""

            candidate = RepositoryCandidate(
                source="gitlab",
                full_name=full_name,
                url=str(item.get("web_url") or ""),
                query=query,
                provider_repository_id=provider_repository_id,
                description=description,
                owner_login=owner_login,
                language="",
                stars=stars,
                topics=tuple(topic_list),
                provider_updated_at=parse_provider_updated_at(
                    item.get("last_activity_at")
                ),
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

"""GitHub repository discovery."""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote_plus

from app.models.signal import RawSignal
from app.sources.common import (
    RepositoryCandidate,
    build_repository_candidate_signal,
)
from app.sources.github.client import GITHUB_API_BASE, fetch_json


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 10,
) -> list[RawSignal]:
    """Search GitHub repositories for topic-derived queries."""

    signals: list[RawSignal] = []
    for query in queries:
        search_url = _build_repository_search_url(
            query, per_query_limit=per_query_limit
        )
        payload = fetch_json(search_url)
        if not isinstance(payload, dict):
            continue

        items = payload.get("items")
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            full_name = str(item.get("full_name") or "").strip()
            if not full_name:
                continue

            description = str(item.get("description") or "")
            topics = item.get("topics")
            topic_list = (
                [str(value) for value in topics] if isinstance(topics, list) else []
            )
            language = str(item.get("language") or "")
            stars = int(item.get("stargazers_count") or 0)
            owner = item.get("owner")
            owner_login = ""
            if isinstance(owner, dict):
                owner_login = str(owner.get("login") or "")

            candidate = RepositoryCandidate(
                source="github",
                full_name=full_name,
                url=str(item.get("html_url") or f"https://github.com/{full_name}"),
                query=query,
                description=description,
                owner_login=owner_login,
                language=language,
                stars=stars,
                topics=tuple(topic_list),
            )
            signals.append(build_repository_candidate_signal(candidate))

    return signals
def _build_repository_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITHUB_API_BASE}/search/repositories"
        f"?q={encoded_query}&sort=updated&order=desc&per_page={per_query_limit}"
    )


def _dedupe_repository_candidates(
    candidates: list[RawSignal],
) -> dict[str, RawSignal]:
    deduped: dict[str, RawSignal] = {}
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

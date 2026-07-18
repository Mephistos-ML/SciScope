"""GitHub repository discovery adapter."""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote_plus

from app.models.signal import RawSignal
from app.sources.github.client import GITHUB_API_BASE, fetch_json


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 5,
) -> list[RawSignal]:
    """Search GitHub repositories for topic-derived queries."""

    signals: list[RawSignal] = []
    for query in queries:
        search_url = _build_repository_search_url(query, per_query_limit=per_query_limit)
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
            topic_list = [str(value) for value in topics] if isinstance(topics, list) else []
            language = str(item.get("language") or "")
            stars = int(item.get("stargazers_count") or 0)
            owner = item.get("owner")
            owner_login = ""
            if isinstance(owner, dict):
                owner_login = str(owner.get("login") or "")

            signals.append(
                RawSignal(
                    source="github",
                    source_type="github_repository",
                    item_id=f"github:repo:{full_name}",
                    title=full_name,
                    url=str(item.get("html_url") or f"https://github.com/{full_name}"),
                    published_at=None,
                    raw_text=_build_repository_text(
                        full_name=full_name,
                        description=description,
                        topics=topic_list,
                        language=language,
                    ),
                    payload={
                        "signal_kind": "github_repository",
                        "repo": full_name,
                        "author": owner_login,
                        "topics": topic_list,
                        "language": language,
                        "stars": stars,
                        "query": query,
                    },
                )
            )

    return signals


def _build_repository_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITHUB_API_BASE}/search/repositories"
        f"?q={encoded_query}&sort=updated&order=desc&per_page={per_query_limit}"
    )


def _build_repository_text(
    *,
    full_name: str,
    description: str,
    topics: Sequence[str],
    language: str,
) -> str:
    parts: list[str] = [full_name, description]
    if topics:
        parts.append(" ".join(topic.strip() for topic in topics if topic.strip()))
    if language.strip():
        parts.append(language.strip())
    return "\n".join(part.strip() for part in parts if part.strip())

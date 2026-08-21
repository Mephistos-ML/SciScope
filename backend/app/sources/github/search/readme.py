"""GitHub README-aware repository search."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from urllib.parse import quote_plus

from app.models.signal import Signal
from app.sources.common import (
    RepositoryCandidate,
    build_repository_candidate_signal,
)
from app.sources.github.client import GITHUB_API_BASE, fetch_json


def discover_repository_candidates_from_readme(
    queries: Sequence[str],
    *,
    per_query_limit: int = 10,
) -> list[Signal]:
    """Search GitHub README files and lift matched repositories into candidates."""

    signals: list[Signal] = []
    readme_cache: dict[str, str] = {}

    for query in queries:
        search_url = _build_code_search_url(query, per_query_limit=per_query_limit)
        payload = fetch_json(search_url)
        if not isinstance(payload, dict):
            continue

        items = payload.get("items")
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            repository = item.get("repository")
            if not isinstance(repository, dict):
                continue

            full_name = str(repository.get("full_name") or "").strip()
            if not full_name:
                continue

            readme_excerpt = readme_cache.get(full_name)
            if readme_excerpt is None:
                readme_excerpt = _load_readme_excerpt(full_name)
                readme_cache[full_name] = readme_excerpt

            owner = repository.get("owner")
            owner_login = ""
            if isinstance(owner, dict):
                owner_login = str(owner.get("login") or "")

            description = _build_candidate_description(
                repository_description=str(repository.get("description") or ""),
                readme_excerpt=readme_excerpt,
            )

            candidate = RepositoryCandidate(
                source="github",
                full_name=full_name,
                url=str(
                    repository.get("html_url") or f"https://github.com/{full_name}"
                ),
                query=query,
                description=description,
                owner_login=owner_login,
                language=str(repository.get("language") or ""),
                stars=int(repository.get("stargazers_count") or 0),
                topics=(),
            )
            signals.append(build_repository_candidate_signal(candidate))

    return signals


def _build_code_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(f"{query} in:file filename:README.md")
    return f"{GITHUB_API_BASE}/search/code?q={encoded_query}&per_page={per_query_limit}"


def _load_readme_excerpt(full_name: str) -> str:
    encoded_name = quote_plus(full_name)
    payload = fetch_json(f"{GITHUB_API_BASE}/repos/{encoded_name}/readme")
    if not isinstance(payload, dict):
        return ""

    raw_content = str(payload.get("content") or "")
    if not raw_content.strip():
        return ""

    try:
        content = base64.b64decode(raw_content).decode("utf-8", errors="ignore")
    except Exception:
        return ""

    return _truncate_excerpt(content)


def _build_candidate_description(
    *,
    repository_description: str,
    readme_excerpt: str,
) -> str:
    parts = [repository_description.strip(), readme_excerpt.strip()]
    return "\n".join(part for part in parts if part)


def _truncate_excerpt(content: str, *, max_length: int = 1200) -> str:
    normalized_lines = [line.strip() for line in content.splitlines() if line.strip()]
    excerpt = "\n".join(normalized_lines)
    if len(excerpt) <= max_length:
        return excerpt
    return excerpt[:max_length].rstrip() + "..."

"""GitHub code-aware repository search."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from time import monotonic
from urllib.parse import quote_plus

from app.models.signal import Signal
from app.sources.common import (
    RepositoryCandidate,
    build_repository_candidate_signal,
    raise_source_timeout_error,
)
from app.sources.common import RepositorySourceError
from app.sources.github.client import GITHUB_API_BASE, fetch_json

logger = logging.getLogger(__name__)


def discover_repository_candidates_from_code(
    queries: Sequence[str],
    *,
    deadline_monotonic: float | None = None,
    per_query_limit: int = 100,
    max_pages: int = 2,
) -> list[Signal]:
    """Search GitHub code and lift matched repositories into candidates."""

    signals: list[Signal] = []

    for query in queries:
        for page in range(1, max_pages + 1):
            if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
                raise_source_timeout_error(source="github", operation="code search")
            search_url = _build_code_search_url(
                query,
                per_query_limit=per_query_limit,
                page=page,
            )
            try:
                if deadline_monotonic is None:
                    payload = fetch_json(search_url)
                else:
                    payload = fetch_json(search_url, deadline_monotonic=deadline_monotonic)
            except RepositorySourceError:
                logger.warning(
                    "GitHub code search request failed for query=%r url=%s",
                    query,
                    search_url,
                    exc_info=True,
                )
                raise
            except Exception:
                logger.exception(
                    "GitHub code search request crashed for query=%r url=%s",
                    query,
                    search_url,
                )
                raise
            if not isinstance(payload, dict):
                break

            items = payload.get("items")
            if not isinstance(items, list) or not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue

                repository = item.get("repository")
                if not isinstance(repository, dict):
                    continue

                full_name = str(repository.get("full_name") or "").strip()
                if not full_name:
                    continue

                owner = repository.get("owner")
                owner_login = ""
                if isinstance(owner, dict):
                    owner_login = str(owner.get("login") or "")

                description = _build_candidate_description(
                    repository_description=str(repository.get("description") or ""),
                    code_path=str(item.get("path") or ""),
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

            if len(items) < per_query_limit:
                break

    return signals


def _build_code_search_url(query: str, *, per_query_limit: int, page: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITHUB_API_BASE}/search/code"
        f"?q={encoded_query}&per_page={per_query_limit}&page={page}"
    )


def _build_candidate_description(
    *,
    repository_description: str,
    code_path: str,
) -> str:
    path_excerpt = f"Matched code path: {code_path.strip()}" if code_path.strip() else ""
    parts = [repository_description.strip(), path_excerpt]
    return "\n".join(part for part in parts if part)

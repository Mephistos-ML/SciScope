"""GitLab code-aware repository search."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from time import monotonic
from urllib.parse import quote_plus

from app.models.signal import Signal
from app.sources.common import (
    RepositoryCandidate,
    RepositorySourceError,
    build_repository_candidate_signal,
    raise_source_timeout_error,
)
from app.sources.gitlab.client import GITLAB_API_BASE, fetch_json

logger = logging.getLogger(__name__)


def discover_repository_candidates_from_code(
    queries: Sequence[str],
    *,
    deadline_monotonic: float | None = None,
    per_query_limit: int = 50,
) -> list[Signal]:
    """Search GitLab code blobs and lift matched projects into candidates."""

    signals: list[Signal] = []
    project_cache: dict[int, dict[str, object] | None] = {}

    for query in queries:
        if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
            raise_source_timeout_error(source="gitlab", operation="code search")
        search_url = _build_blob_search_url(query, per_query_limit=per_query_limit)
        try:
            if deadline_monotonic is None:
                payload = fetch_json(search_url)
            else:
                payload = fetch_json(search_url, deadline_monotonic=deadline_monotonic)
        except RepositorySourceError:
            logger.warning(
                "GitLab code search request failed for query=%r url=%s",
                query,
                search_url,
                exc_info=True,
            )
            raise
        except Exception:
            logger.exception(
                "GitLab code search request crashed for query=%r url=%s",
                query,
                search_url,
            )
            raise
        if not isinstance(payload, list):
            continue

        for item in payload:
            if not isinstance(item, dict):
                continue

            project_id = item.get("project_id")
            if not isinstance(project_id, int):
                continue

            project = project_cache.get(project_id)
            if project is None:
                try:
                    project = _load_project_metadata(
                        project_id,
                        deadline_monotonic=deadline_monotonic,
                    )
                except RepositorySourceError:
                    logger.warning(
                        "GitLab project metadata fetch failed for project_id=%s query=%r",
                        project_id,
                        query,
                        exc_info=True,
                    )
                    project = None
                except Exception:
                    logger.exception(
                        "GitLab project metadata fetch crashed for project_id=%s query=%r",
                        project_id,
                        query,
                    )
                    project = None
                project_cache[project_id] = project
            if not isinstance(project, dict):
                continue

            full_name = str(project.get("path_with_namespace") or "").strip()
            if not full_name:
                continue

            owner_login = full_name.split("/", 1)[0] if "/" in full_name else ""
            topics = project.get("topics")
            topic_list = [str(value) for value in topics] if isinstance(topics, list) else []

            candidate = RepositoryCandidate(
                source="gitlab",
                full_name=full_name,
                url=str(project.get("web_url") or ""),
                query=query,
                description=str(project.get("description") or ""),
                owner_login=owner_login,
                language="",
                stars=int(project.get("star_count") or 0),
                topics=tuple(topic_list),
                matched_path=str(item.get("path") or ""),
                matched_excerpt=str(item.get("data") or ""),
            )
            signals.append(build_repository_candidate_signal(candidate))

    return signals


def _build_blob_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITLAB_API_BASE}/search"
        f"?scope=blobs&search={encoded_query}&per_page={per_query_limit}"
    )


def _load_project_metadata(
    project_id: int,
    *,
    deadline_monotonic: float | None = None,
) -> dict[str, object] | None:
    if deadline_monotonic is None:
        payload = fetch_json(f"{GITLAB_API_BASE}/projects/{project_id}")
    else:
        payload = fetch_json(
            f"{GITLAB_API_BASE}/projects/{project_id}",
            deadline_monotonic=deadline_monotonic,
        )
    if isinstance(payload, dict):
        return payload
    return None

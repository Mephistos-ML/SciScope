"""GitLab code-aware repository search."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from urllib.parse import quote_plus

from app.models.signal import Signal
from app.sources.common import (
    RepositoryCandidate,
    RepositorySourceError,
    build_repository_candidate_signal,
)
from app.sources.gitlab.client import GITLAB_API_BASE, fetch_json

logger = logging.getLogger(__name__)


def discover_repository_candidates_from_code(
    queries: Sequence[str],
    *,
    per_query_limit: int = 50,
) -> list[Signal]:
    """Search GitLab code blobs and lift matched projects into candidates."""

    signals: list[Signal] = []
    project_cache: dict[int, dict[str, object] | None] = {}

    for query in queries:
        search_url = _build_blob_search_url(query, per_query_limit=per_query_limit)
        try:
            payload = fetch_json(search_url)
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
                    project = _load_project_metadata(project_id)
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

            description = _build_candidate_description(
                project_description=str(project.get("description") or ""),
                code_path=str(item.get("path") or ""),
                code_excerpt=str(item.get("data") or ""),
            )
            owner_login = full_name.split("/", 1)[0] if "/" in full_name else ""
            topics = project.get("topics")
            topic_list = [str(value) for value in topics] if isinstance(topics, list) else []

            candidate = RepositoryCandidate(
                source="gitlab",
                full_name=full_name,
                url=str(project.get("web_url") or ""),
                query=query,
                description=description,
                owner_login=owner_login,
                language="",
                stars=int(project.get("star_count") or 0),
                topics=tuple(topic_list),
            )
            signals.append(build_repository_candidate_signal(candidate))

    return signals


def _build_blob_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITLAB_API_BASE}/search"
        f"?scope=blobs&search={encoded_query}&per_page={per_query_limit}"
    )


def _load_project_metadata(project_id: int) -> dict[str, object] | None:
    payload = fetch_json(f"{GITLAB_API_BASE}/projects/{project_id}")
    if isinstance(payload, dict):
        return payload
    return None


def _build_candidate_description(
    *,
    project_description: str,
    code_path: str,
    code_excerpt: str,
) -> str:
    path_excerpt = f"Matched code path: {code_path.strip()}" if code_path.strip() else ""
    parts = [project_description.strip(), path_excerpt, code_excerpt.strip()]
    return "\n".join(part for part in parts if part)

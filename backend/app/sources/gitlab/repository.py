"""Canonical GitLab project profiles addressed by immutable provider ID."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import quote, unquote, urlsplit

from app.config import GITLAB_BASE_URL
from app.models.repository import Repository, build_repository_id, parse_provider_updated_at
from app.sources.common.source_status import RepositorySourceError
from app.sources.gitlab.client import GITLAB_API_BASE, fetch_json


def load_repository_profile(provider_repository_id: str) -> Repository:
    try:
        response = fetch_json(
            f"{GITLAB_API_BASE}/projects/{quote(provider_repository_id, safe='')}"
        )
    except ValueError as exc:
        raise _invalid_profile() from exc
    repository = map_repository_profile(response.payload)
    if repository.provider_repository_id != provider_repository_id:
        raise _invalid_profile()
    try:
        languages = fetch_json(
            f"{GITLAB_API_BASE}/projects/{quote(provider_repository_id, safe='')}/languages"
        ).payload
    except ValueError as exc:
        raise _invalid_profile() from exc
    if not isinstance(languages, dict) or any(
        not isinstance(percentage, (float, int)) for percentage in languages.values()
    ):
        raise _invalid_profile()
    return replace(repository, language=max(languages, key=languages.get) if languages else "")


def map_repository_profile(payload: object) -> Repository:
    if not isinstance(payload, dict):
        raise _invalid_profile()
    provider_id = str(payload.get("id") or "")
    full_name = str(payload.get("path_with_namespace") or "").strip()
    url = str(payload.get("web_url") or "").strip()
    base = urlsplit(GITLAB_BASE_URL)
    if (
        not provider_id.isascii() or not provider_id.isdecimal() or int(provider_id) <= 0
        or not full_name or urlsplit(url).scheme != base.scheme
        or urlsplit(url).netloc != base.netloc
        or unquote(urlsplit(url).path).rstrip("/") != f"{unquote(base.path).rstrip('/')}/{full_name}"
    ):
        raise _invalid_profile()
    topics = payload.get("topics")
    try:
        stars = int(payload.get("star_count") or 0)
    except (TypeError, ValueError) as exc:
        raise _invalid_profile() from exc
    return Repository(
        repository_id=build_repository_id("gitlab", provider_id),
        source="gitlab",
        provider_repository_id=provider_id,
        full_name=full_name,
        url=url,
        owner_login=full_name.split("/", 1)[0],
        description=str(payload.get("description") or ""),
        stars=stars,
        topics=tuple(str(topic) for topic in topics) if isinstance(topics, list) else (),
        provider_updated_at=parse_provider_updated_at(payload.get("last_activity_at")),
        metadata={"repo": full_name},
    )


def _invalid_profile() -> RepositorySourceError:
    return RepositorySourceError(
        source="gitlab", status="error",
        public_message="GitLab returned an invalid repository profile.",
    )

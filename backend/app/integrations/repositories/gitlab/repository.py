"""Canonical GitLab project profiles addressed by immutable provider ID."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import quote, unquote, urlsplit

from app.models.repository import (
    Repository, build_repository_id, parse_provider_updated_at, validate_provider_repository_id,
)
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.gitlab.client import GitLabClient


def load_repository_profile(provider_repository_id: str, *, client: GitLabClient) -> Repository:
    try:
        response = client.fetch_json(
            f"{client.api_base}/projects/{quote(provider_repository_id, safe='')}"
        )
    except ValueError as exc:
        raise _invalid_profile() from exc
    repository = map_repository_profile(response.payload, base_url=client.base_url)
    if repository.provider_repository_id != provider_repository_id:
        raise _invalid_profile()
    try:
        languages = client.fetch_json(
            f"{client.api_base}/projects/{quote(provider_repository_id, safe='')}/languages"
        ).payload
    except ValueError as exc:
        raise _invalid_profile() from exc
    if not isinstance(languages, dict) or any(
        not isinstance(percentage, (float, int)) for percentage in languages.values()
    ):
        raise _invalid_profile()
    return replace(repository, language=max(languages, key=languages.get) if languages else "")


def map_repository_profile(payload: object, *, base_url: str) -> Repository:
    if not isinstance(payload, dict):
        raise _invalid_profile()
    provider_id = str(payload.get("id") or "")
    try:
        validate_provider_repository_id(provider_id)
    except ValueError as exc:
        raise _invalid_profile() from exc
    full_name = str(payload.get("path_with_namespace") or "").strip()
    url = str(payload.get("web_url") or "").strip()
    base = urlsplit(base_url)
    if (
        not full_name or urlsplit(url).scheme != base.scheme
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

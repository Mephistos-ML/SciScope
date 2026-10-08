"""Canonical GitHub repository profiles addressed by immutable provider ID."""

from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit

from app.models.repository import Repository, build_repository_id, parse_provider_updated_at
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github.client import GitHubClient


def load_repository_profile(provider_repository_id: str, *, client: GitHubClient) -> Repository:
    try:
        response = client.fetch_json(
            f"{client.api_base}/repositories/{quote(provider_repository_id, safe='')}"
        )
    except ValueError as exc:
        raise _invalid_profile() from exc
    repository = map_repository_profile(response.payload)
    if repository.provider_repository_id != provider_repository_id:
        raise _invalid_profile()
    return repository


def map_repository_profile(payload: object) -> Repository:
    if not isinstance(payload, dict):
        raise _invalid_profile()
    provider_id = str(payload.get("id") or "")
    full_name = str(payload.get("full_name") or "").strip()
    url = str(payload.get("html_url") or "").strip()
    if (
        not provider_id.isascii() or not provider_id.isdecimal() or int(provider_id) <= 0
        or not full_name or urlsplit(url).scheme != "https"
        or urlsplit(url).netloc != "github.com"
        or unquote(urlsplit(url).path).rstrip("/") != f"/{full_name}"
    ):
        raise _invalid_profile()
    owner = payload.get("owner")
    topics = payload.get("topics")
    try:
        stars = int(payload.get("stargazers_count") or 0)
    except (TypeError, ValueError) as exc:
        raise _invalid_profile() from exc
    return Repository(
        repository_id=build_repository_id("github", provider_id),
        source="github",
        provider_repository_id=provider_id,
        full_name=full_name,
        url=url,
        owner_login=str(owner.get("login") or "") if isinstance(owner, dict) else "",
        description=str(payload.get("description") or ""),
        language=str(payload.get("language") or ""),
        stars=stars,
        topics=tuple(str(topic) for topic in topics) if isinstance(topics, list) else (),
        provider_updated_at=parse_provider_updated_at(payload.get("updated_at")),
        metadata={"repo": full_name},
    )


def _invalid_profile() -> RepositorySourceError:
    return RepositorySourceError(
        source="github", status="error",
        public_message="GitHub returned an invalid repository profile.",
    )

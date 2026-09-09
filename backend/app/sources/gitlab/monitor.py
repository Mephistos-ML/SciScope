"""GitLab monitoring adapter for repository releases and commits."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import quote_plus

from app.models.repository import Repository, RepositoryActivity
from app.models.signal import Signal
from app.sources.common import (
    RepositoryCommit,
    RepositoryRelease,
    build_repository_main_commit_signal,
    build_repository_release_signal,
)
from app.sources.gitlab.client import (
    GITLAB_API_BASE,
    fetch_json,
)


def load_repo_activity(
    repo_full_name: str,
    *,
    release_started_after: datetime | None,
    commit_started_after: datetime | None,
) -> RepositoryActivity:
    """Load repository activity and report whether its provider URL redirected."""

    signals: list[Signal] = []
    redirected = False
    if release_started_after is not None:
        release_signals, release_redirected = _load_release_signals(
            repo_full_name,
            started_after=release_started_after,
        )
        signals.extend(release_signals)
        redirected = redirected or release_redirected
    if commit_started_after is not None:
        commit_signals, commit_redirected = _load_commit_signals(
            repo_full_name,
            started_after=commit_started_after,
        )
        signals.extend(commit_signals)
        redirected = redirected or commit_redirected
    return RepositoryActivity(signals=tuple(signals), redirected=redirected)


def refresh_repository_profile(repository: Repository) -> Repository:
    """Load the canonical GitLab profile by immutable provider project ID."""

    provider_repository_id = repository.provider_repository_id.strip()
    if not provider_repository_id:
        return repository

    response = fetch_json(
        f"{GITLAB_API_BASE}/projects/{quote_plus(provider_repository_id)}"
    )
    payload = response.payload
    if not isinstance(payload, dict):
        return repository

    full_name = str(payload.get("path_with_namespace") or "").strip()
    url = str(payload.get("web_url") or "").strip()
    if not full_name or not url:
        return repository
    metadata = dict(repository.metadata)
    metadata["repo"] = full_name
    return replace(repository, full_name=full_name, url=url, metadata=metadata)

def _load_release_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> tuple[list[Signal], bool]:
    encoded_repo = quote_plus(repo_full_name)
    releases_url = f"{GITLAB_API_BASE}/projects/{encoded_repo}/releases?per_page=10"
    response = fetch_json(releases_url)
    payload = response.payload

    if not isinstance(payload, list):
        return [], response.url != releases_url

    signals: list[Signal] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        published_at = _parse_gitlab_datetime(
            item.get("released_at") or item.get("created_at"),
        )
        if published_at is None or published_at <= started_after:
            continue

        title = str(item.get("name") or item.get("tag_name") or "GitLab release")
        body = str(item.get("description") or "")
        tag_name = str(item.get("tag_name") or "")
        release_id = tag_name or title

        release = RepositoryRelease(
            source="gitlab",
            repo_full_name=repo_full_name,
            release_id=release_id,
            title=title,
            url=str(
                item.get("_links", {}).get("self")
                if isinstance(item.get("_links"), dict)
                else item.get("commit_path")
                or f"https://gitlab.com/{repo_full_name}/-/releases"
            ),
            published_at=published_at,
            tag_name=tag_name,
            body=body,
        )
        signals.append(build_repository_release_signal(release))

    return signals, response.url != releases_url


def _load_commit_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> tuple[list[Signal], bool]:
    encoded_repo = quote_plus(repo_full_name)
    commits_url = (
        f"{GITLAB_API_BASE}/projects/{encoded_repo}/repository/commits?per_page=10"
    )
    response = fetch_json(commits_url)
    payload = response.payload

    if not isinstance(payload, list):
        return [], response.url != commits_url

    signals: list[Signal] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        published_at = _parse_gitlab_datetime(
            item.get("committed_date") or item.get("created_at"),
        )
        if published_at is None or published_at <= started_after:
            continue

        commit_sha = str(item.get("id") or "").strip()
        if not commit_sha:
            continue

        message = str(item.get("message") or item.get("title") or "").strip()
        title = str(item.get("title") or message.splitlines()[0] or "GitLab commit")
        commit = RepositoryCommit(
            source="gitlab",
            repo_full_name=repo_full_name,
            commit_sha=commit_sha,
            title=title.strip(),
            url=str(
                item.get("web_url")
                or f"https://gitlab.com/{repo_full_name}/-/commit/{commit_sha}"
            ),
            published_at=published_at,
            branch="default",
            author_name=str(item.get("author_name") or ""),
            body=message,
        )
        signals.append(build_repository_main_commit_signal(commit))

    return signals, response.url != commits_url



def _parse_gitlab_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

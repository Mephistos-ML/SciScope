"""GitHub monitoring adapter for repository releases and commits."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from app.models.repository import Repository, RepositoryActivity
from app.models.signal import Signal
from app.sources.common import (
    RepositoryCommit,
    RepositoryRelease,
    build_repository_main_commit_signal,
    build_repository_release_signal,
)
from app.sources.github.client import (
    GITHUB_API_BASE,
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
    """Load the canonical GitHub profile by immutable provider repository ID."""

    provider_repository_id = repository.provider_repository_id.strip()
    if not provider_repository_id:
        return repository

    response = fetch_json(
        f"{GITHUB_API_BASE}/repositories/{provider_repository_id}"
    )
    payload = response.payload
    if not isinstance(payload, dict):
        return repository

    full_name = str(payload.get("full_name") or "").strip()
    url = str(payload.get("html_url") or "").strip()
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
    releases_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/releases?per_page=10"
    response = fetch_json(releases_url)
    payload = response.payload

    if not isinstance(payload, list):
        return [], response.url != releases_url

    signals: list[Signal] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        published_at = _parse_github_datetime(
            item.get("published_at") or item.get("created_at"),
        )
        if published_at is None or published_at <= started_after:
            continue

        title = str(item.get("name") or item.get("tag_name") or "GitHub release")
        body = str(item.get("body") or "")
        tag_name = str(item.get("tag_name") or "")
        release_id = str(item.get("id") or tag_name or title)

        release = RepositoryRelease(
            source="github",
            repo_full_name=repo_full_name,
            release_id=release_id,
            title=title,
            url=str(
                item.get("html_url")
                or f"https://github.com/{repo_full_name}/releases"
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
    commits_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/commits?per_page=10"
    response = fetch_json(commits_url)
    payload = response.payload

    if not isinstance(payload, list):
        return [], response.url != commits_url

    signals: list[Signal] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        commit_payload = item.get("commit")
        if not isinstance(commit_payload, dict):
            continue

        author_payload = commit_payload.get("author")
        if not isinstance(author_payload, dict):
            author_payload = {}

        published_at = _parse_github_datetime(author_payload.get("date"))
        if published_at is None or published_at <= started_after:
            continue

        commit_sha = str(item.get("sha") or "").strip()
        if not commit_sha:
            continue

        message = str(commit_payload.get("message") or "").strip()
        title = message.splitlines()[0].strip() if message else "GitHub commit"
        commit = RepositoryCommit(
            source="github",
            repo_full_name=repo_full_name,
            commit_sha=commit_sha,
            title=title,
            url=str(
                item.get("html_url")
                or f"https://github.com/{repo_full_name}/commit/{commit_sha}"
            ),
            published_at=published_at,
            branch="default",
            author_name=str(author_payload.get("name") or ""),
            body=message,
        )
        signals.append(build_repository_main_commit_signal(commit))

    return signals, response.url != commits_url


def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

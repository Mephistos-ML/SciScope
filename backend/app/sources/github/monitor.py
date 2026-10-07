"""GitHub monitoring adapter for repository releases and commits."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from app.models.repository import Repository
from app.models.signal import Signal
from app.sources.common import (
    RepositoryActivity,
    RepositoryCommit,
    RepositoryRelease,
    build_repository_main_commit_signal,
    build_repository_release_signal,
    read_repository_name,
)
from app.sources.common.models import RepositoryActivityBatch
from app.sources.github.client import (
    GITHUB_API_BASE,
    fetch_json,
)


def load_repository_activity(
    repository: Repository,
    *,
    release_started_after: datetime | None,
    commit_started_after: datetime | None,
) -> RepositoryActivity:
    """Load repository activity and report whether its provider URL redirected."""

    repo_full_name = read_repository_name(repository)
    if repo_full_name is None:
        return RepositoryActivity(signals=(), releases_complete=False, commits_complete=False)

    releases = RepositoryActivityBatch(signals=(), complete=True)
    commits = RepositoryActivityBatch(signals=(), complete=True)
    if release_started_after is not None:
        releases = _load_release_signals(repo_full_name, started_after=release_started_after)
    if commit_started_after is not None:
        commits = _load_commit_signals(repo_full_name, started_after=commit_started_after)
    return RepositoryActivity(
        signals=(*releases.signals, *commits.signals),
        releases_complete=releases.complete, commits_complete=commits.complete,
        redirected=releases.redirected or commits.redirected,
    )


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
) -> RepositoryActivityBatch:
    releases_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/releases?per_page=10"
    response = fetch_json(releases_url)
    payload = response.payload

    if not isinstance(payload, list):
        return RepositoryActivityBatch(signals=(), complete=False, redirected=response.url != releases_url)

    complete = len(payload) < 10
    signals: list[Signal] = []
    for item in payload:
        if not isinstance(item, dict):
            complete = False
            continue

        published_at = _parse_github_datetime(
            item.get("published_at") or item.get("created_at"),
        )
        if published_at is None:
            complete = False
            continue
        if published_at <= started_after:
            continue

        title = str(item.get("name") or item.get("tag_name") or "GitHub release")
        body = str(item.get("body") or "")
        tag_name = str(item.get("tag_name") or "")
        if not (item.get("id") or tag_name):
            complete = False
            continue
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

    return RepositoryActivityBatch(signals=tuple(signals), complete=complete, redirected=response.url != releases_url)


def _load_commit_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> RepositoryActivityBatch:
    commits_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/commits?per_page=10"
    response = fetch_json(commits_url)
    payload = response.payload

    if not isinstance(payload, list):
        return RepositoryActivityBatch(signals=(), complete=False, redirected=response.url != commits_url)

    complete = len(payload) < 10
    signals: list[Signal] = []
    for item in payload:
        if not isinstance(item, dict):
            complete = False
            continue

        commit_payload = item.get("commit")
        if not isinstance(commit_payload, dict):
            complete = False
            continue

        author_payload = commit_payload.get("author")
        if not isinstance(author_payload, dict):
            author_payload = {}

        published_at = _parse_github_datetime(author_payload.get("date"))
        if published_at is None:
            complete = False
            continue
        if published_at <= started_after:
            continue

        commit_sha = str(item.get("sha") or "").strip()
        if not commit_sha:
            complete = False
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

    return RepositoryActivityBatch(signals=tuple(signals), complete=complete, redirected=response.url != commits_url)


def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

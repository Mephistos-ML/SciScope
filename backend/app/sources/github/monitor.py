"""GitHub monitoring adapter for repository releases and commits."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.signal import Signal
from app.sources.common import (
    RepositoryCommit,
    RepositoryRelease,
    build_repository_main_commit_signal,
    build_repository_release_signal,
)
from app.sources.github.client import GITHUB_API_BASE, fetch_json


def load_repo_activity(
    repo_full_name: str,
    *,
    release_started_after: datetime | None,
    commit_started_after: datetime | None,
) -> list[Signal]:
    """Load releases and default-branch commits created after their checkpoints."""

    signals: list[Signal] = []
    if release_started_after is not None:
        signals.extend(
            _load_release_signals(
                repo_full_name,
                started_after=release_started_after,
            )
        )
    if commit_started_after is not None:
        signals.extend(
            _load_commit_signals(
                repo_full_name,
                started_after=commit_started_after,
            )
        )
    return signals

def _load_release_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> list[Signal]:
    releases_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/releases?per_page=10"
    payload = fetch_json(releases_url)

    if not isinstance(payload, list):
        return []

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

    return signals


def _load_commit_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> list[Signal]:
    commits_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/commits?per_page=10"
    payload = fetch_json(commits_url)

    if not isinstance(payload, list):
        return []

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

    return signals


def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

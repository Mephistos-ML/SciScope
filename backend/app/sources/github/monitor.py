"""GitHub monitoring adapter for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.repository import Repository
from app.models.signal import Signal
from app.runtime.state import STATE
from app.sources.common import (
    RepositoryRelease,
    build_repository_release_checkpoint,
    build_repository_release_signal,
    read_repository_name,
)
from app.sources.github.client import GITHUB_API_BASE, fetch_json
from app.sources.github.state import resolve_release_checkpoint
from app.storage.repositories import upsert_repository_checkpoints

build_release_checkpoint = build_repository_release_checkpoint


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[Signal]:
    """Load releases created after the monitoring start time."""

    if started_after is None:
        return []

    return _load_release_signals(repo_full_name, started_after=started_after)


def load_github_signals_for_subscription(
    subscription_id: str,
    repository: Repository,
    *,
    database_url: str,
) -> list[Signal]:
    """Load live GitHub release signals for one watched repository."""

    baseline_started_after = STATE.monitoring_started_at
    repo_name = read_repository_name(repository)
    if repo_name is None:
        return []

    started_after = resolve_release_checkpoint(
        subscription_id,
        repository,
        baseline_started_after=baseline_started_after,
        database_url=database_url,
    )
    if started_after is None:
        return []

    signals = load_repo_activity(
        repo_name,
        started_after=started_after,
    )
    latest_published_at = max(
        (
            signal.published_at
            for signal in signals
            if signal.published_at is not None
        ),
        default=started_after,
    )
    checkpoint = build_repository_release_checkpoint(
        subscription_id,
        repository,
        latest_published_at=latest_published_at,
        fallback_started_after=started_after,
    )
    if checkpoint is not None:
        upsert_repository_checkpoints((checkpoint,), database_url=database_url)

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


def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

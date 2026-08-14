"""GitLab monitoring adapter for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote_plus

from app.models.repository import Repository
from app.models.signal import Signal
from app.runtime.state import STATE
from app.sources.common import (
    RepositoryRelease,
    build_repository_release_checkpoint,
    build_repository_release_signal,
    read_repository_name,
)
from app.sources.gitlab.client import GITLAB_API_BASE, fetch_json
from app.sources.gitlab.state import resolve_release_checkpoint
from app.storage.repositories import upsert_repository_checkpoints

build_release_checkpoint = build_repository_release_checkpoint


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[Signal]:
    """Load GitLab releases created after the monitoring start time."""

    if started_after is None:
        return []

    return _load_release_signals(repo_full_name, started_after=started_after)


def load_gitlab_signals_for_subscription(
    subscription_id: str,
    repository: Repository,
) -> list[Signal]:
    """Load live GitLab release signals for one watched repository."""

    baseline_started_after = STATE.monitoring_started_at
    repo_name = read_repository_name(repository)
    if repo_name is None:
        return []

    started_after = resolve_release_checkpoint(
        subscription_id,
        repository,
        baseline_started_after=baseline_started_after,
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
        upsert_repository_checkpoints((checkpoint,))

    return signals


def _load_release_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> list[Signal]:
    encoded_repo = quote_plus(repo_full_name)
    releases_url = f"{GITLAB_API_BASE}/projects/{encoded_repo}/releases?per_page=10"
    payload = fetch_json(releases_url)

    if not isinstance(payload, list):
        return []

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

    return signals


def _parse_gitlab_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

"""GitHub monitoring adapter for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.signal import RawSignal
from app.runtime.state import STATE
from app.sources.repositories.common import (
    RepositoryRelease,
    build_repository_release_checkpoint,
    build_repository_release_signal,
    read_repository_name,
)
from app.sources.repositories.github.client import GITHUB_API_BASE, fetch_json
from app.sources.repositories.github.state import (
    load_watched_github_repository_entities,
    resolve_release_checkpoint,
)
from app.storage.entities import upsert_entity_checkpoints

build_release_checkpoint = build_repository_release_checkpoint


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[RawSignal]:
    """Load releases created after the monitoring start time."""

    if started_after is None:
        return []

    return _load_release_signals(repo_full_name, started_after=started_after)


def load_github_signals_for_profile(profile) -> list[RawSignal]:
    """Load live GitHub release signals for watched repositories."""

    baseline_started_after = STATE.monitoring_started_at
    watched_repositories = load_watched_github_repository_entities(profile.topic_slug)
    signals: list[RawSignal] = []
    checkpoints_to_upsert = []

    for entity in watched_repositories:
        repo_name = read_repository_name(entity)
        if repo_name is None:
            continue

        started_after = resolve_release_checkpoint(
            profile.topic_slug,
            entity,
            baseline_started_after=baseline_started_after,
        )
        if started_after is None:
            continue

        repo_signals = load_repo_activity(
            repo_name,
            started_after=started_after,
        )
        signals.extend(repo_signals)

        latest_published_at = max(
            (
                signal.published_at
                for signal in repo_signals
                if signal.published_at is not None
            ),
            default=started_after,
        )
        checkpoint = build_repository_release_checkpoint(
            profile.topic_slug,
            entity,
            latest_published_at=latest_published_at,
            fallback_started_after=started_after,
        )
        if checkpoint is not None:
            checkpoints_to_upsert.append(checkpoint)

    upsert_entity_checkpoints(checkpoints_to_upsert)
    return signals


def _load_release_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> list[RawSignal]:
    releases_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/releases?per_page=10"
    payload = fetch_json(releases_url)

    if not isinstance(payload, list):
        return []

    signals: list[RawSignal] = []
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

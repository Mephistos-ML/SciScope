"""GitLab monitoring adapter for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote_plus

from app.models.signal import RawSignal
from app.runtime.state import STATE
from app.sources.repositories.common import (
    RepositoryRelease,
    build_repository_release_checkpoint,
    build_repository_release_signal,
    read_repository_name,
)
from app.sources.repositories.gitlab.client import GITLAB_API_BASE, fetch_json
from app.sources.repositories.gitlab.state import (
    load_watched_gitlab_repository_entities,
    resolve_release_checkpoint,
)
from app.storage.entities import upsert_entity_checkpoints

build_release_checkpoint = build_repository_release_checkpoint


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[RawSignal]:
    """Load GitLab releases created after the monitoring start time."""

    if started_after is None:
        return []

    return _load_release_signals(repo_full_name, started_after=started_after)


def load_gitlab_signals_for_profile(profile) -> list[RawSignal]:
    """Load live GitLab release signals for watched repositories."""

    baseline_started_after = STATE.monitoring_started_at
    watched_repositories = load_watched_gitlab_repository_entities(profile.topic_slug)
    signals: list[RawSignal] = []
    checkpoints_to_upsert = []

    for entity in watched_repositories:
        repo_name = read_repository_name(entity)
        if repo_name is None:
            continue

        started_after = resolve_release_checkpoint(
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
    encoded_repo = quote_plus(repo_full_name)
    releases_url = f"{GITLAB_API_BASE}/projects/{encoded_repo}/releases?per_page=10"
    payload = fetch_json(releases_url)

    if not isinstance(payload, list):
        return []

    signals: list[RawSignal] = []
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

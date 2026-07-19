"""GitHub monitoring adapter for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.signal import RawSignal
from app.sources.github.client import GITHUB_API_BASE, fetch_json
from app.sources.github.state import (
    build_release_checkpoint,
    load_watched_github_repository_entities,
    read_repo_name,
    resolve_release_checkpoint,
)
from app.runtime.state import STATE
from app.storage.entities import upsert_entity_checkpoints


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
        repo_name = read_repo_name(entity)
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
        checkpoint = build_release_checkpoint(
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

        signals.append(
            RawSignal(
                source="github",
                source_type="github_release",
                item_id=f"{repo_full_name}:release:{release_id}",
                title=f"{repo_full_name} release {title}",
                url=str(
                    item.get("html_url")
                    or f"https://github.com/{repo_full_name}/releases"
                ),
                published_at=published_at,
                raw_text=f"{title}\n\n{body}\n\n{tag_name}".strip(),
                payload={
                    "signal_kind": "github_release",
                    "repo": repo_full_name,
                    "tag_name": tag_name,
                    "source_type": "github_release",
                },
            )
        )

    return signals


def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

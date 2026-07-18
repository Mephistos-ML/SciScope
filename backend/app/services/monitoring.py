"""Monitoring orchestration for watched entities."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entity import Entity, EntityCheckpoint
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile
from app.runtime.state import STATE
from app.sources.github.monitor import load_repo_activity
from app.storage.entities import (
    get_entity_checkpoint,
    list_entities_by_ids,
    list_topic_entity_matches,
    upsert_entity_checkpoints,
)

LATEST_RELEASE_CHECKPOINT_KEY = "latest_release_published_at"


def load_github_signals_for_profile(profile: ResearchProfile) -> list[RawSignal]:
    """Load live GitHub release signals for watched repositories."""

    baseline_started_after = STATE.monitoring_started_at
    watched_repositories = load_watched_github_repository_entities(profile.topic_slug)
    signals: list[RawSignal] = []
    checkpoints_to_upsert: list[EntityCheckpoint] = []

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

        checkpoint = build_release_checkpoint(
            entity,
            repo_signals=repo_signals,
            fallback_started_after=started_after,
        )
        if checkpoint is not None:
            checkpoints_to_upsert.append(checkpoint)

    upsert_entity_checkpoints(checkpoints_to_upsert)
    return signals


def load_watched_github_repository_entities(topic_slug: str) -> tuple[Entity, ...]:
    """Load watched GitHub repository entities for one topic."""

    matches = list_topic_entity_matches(topic_slug)
    entity_ids = [match.entity_id for match in matches if match.source == "github"]
    entities = list_entities_by_ids(entity_ids)

    repos: list[Entity] = []
    for entity in entities:
        if entity.source != "github" or entity.entity_type != "repository":
            continue
        if read_repo_name(entity) is not None:
            repos.append(entity)
    return tuple(repos)


def describe_watched_github_repositories(topic_slug: str) -> list[dict[str, object]]:
    """Return watched repository metadata for debug visibility."""

    repositories = load_watched_github_repository_entities(topic_slug)
    return [
        {
            "entityId": entity.entity_id,
            "repo": read_repo_name(entity),
            "url": entity.url,
            "stars": entity.metadata.get("stars"),
            "query": entity.metadata.get("query"),
            "language": entity.metadata.get("language"),
        }
        for entity in repositories
    ]


def describe_release_checkpoints(topic_slug: str) -> list[dict[str, object]]:
    """Return release checkpoint state for watched repositories."""

    repositories = load_watched_github_repository_entities(topic_slug)
    checkpoints: list[dict[str, object]] = []
    for entity in repositories:
        checkpoint = get_entity_checkpoint(
            entity.entity_id,
            LATEST_RELEASE_CHECKPOINT_KEY,
        )
        checkpoints.append(
            {
                "entityId": entity.entity_id,
                "repo": read_repo_name(entity),
                "checkpointKey": LATEST_RELEASE_CHECKPOINT_KEY,
                "checkpointValue": (
                    checkpoint.checkpoint_value if checkpoint is not None else None
                ),
                "updatedAt": (
                    checkpoint.updated_at.isoformat(timespec="seconds")
                    if checkpoint is not None
                    else None
                ),
            }
        )

    return checkpoints


def read_repo_name(entity: Entity) -> str | None:
    """Read a normalized repo full name from one entity."""

    repo_name = entity.metadata.get("repo")
    if not isinstance(repo_name, str) or not repo_name.strip():
        repo_name = entity.canonical_name
    repo_name = repo_name.strip()
    if repo_name:
        return repo_name
    return None


def resolve_release_checkpoint(
    entity: Entity,
    *,
    baseline_started_after: datetime | None,
) -> datetime | None:
    """Resolve the monitoring cursor for one watched entity."""

    checkpoint = get_entity_checkpoint(
        entity.entity_id,
        LATEST_RELEASE_CHECKPOINT_KEY,
    )
    if checkpoint is not None:
        return datetime.fromisoformat(checkpoint.checkpoint_value).astimezone(UTC)

    return baseline_started_after


def build_release_checkpoint(
    entity: Entity,
    *,
    repo_signals: list[RawSignal],
    fallback_started_after: datetime,
) -> EntityCheckpoint | None:
    """Build the next release cursor for one watched entity."""

    latest_published_at = max(
        (signal.published_at for signal in repo_signals if signal.published_at is not None),
        default=fallback_started_after,
    )
    if latest_published_at is None:
        return None

    return EntityCheckpoint(
        entity_id=entity.entity_id,
        source=entity.source,
        checkpoint_key=LATEST_RELEASE_CHECKPOINT_KEY,
        checkpoint_value=latest_published_at.astimezone(UTC).isoformat(),
        updated_at=datetime.now(UTC),
    )

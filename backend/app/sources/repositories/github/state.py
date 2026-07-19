"""GitHub-specific watched-repository state and checkpoint helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entity import Entity, EntityCheckpoint
from app.models.topic import ResearchProfile
from app.sources.repositories.common import (
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    read_repository_name,
)
from app.storage.entities import (
    get_entity_checkpoint,
    list_entities_by_ids,
    list_topic_entity_matches,
    upsert_entity_checkpoints,
)


def sync_github_baseline_for_profile(profile: ResearchProfile) -> None:
    """Initialize checkpoints for watched repositories that have none yet."""

    watched_repositories = load_watched_github_repository_entities(profile.topic_slug)
    checkpoints_to_upsert: list[EntityCheckpoint] = []

    for entity in watched_repositories:
        repo_name = read_repository_name(entity)
        if repo_name is None:
            continue

        checkpoint = get_entity_checkpoint(
            entity.entity_id,
            REPOSITORY_RELEASE_CHECKPOINT_KEY,
        )
        if checkpoint is not None:
            continue

        now = datetime.now(UTC)
        checkpoints_to_upsert.append(
            EntityCheckpoint(
                entity_id=entity.entity_id,
                source=entity.source,
                checkpoint_key=REPOSITORY_RELEASE_CHECKPOINT_KEY,
                checkpoint_value=now.isoformat(),
                updated_at=now,
            )
        )

    upsert_entity_checkpoints(checkpoints_to_upsert)


def load_watched_github_repository_entities(topic_slug: str) -> tuple[Entity, ...]:
    """Load watched GitHub repository entities for one topic."""

    matches = list_topic_entity_matches(topic_slug)
    entity_ids = [match.entity_id for match in matches if match.source == "github"]
    entities = list_entities_by_ids(entity_ids)

    repos: list[Entity] = []
    for entity in entities:
        if entity.source != "github" or entity.entity_type != "repository":
            continue
        if read_repository_name(entity) is not None:
            repos.append(entity)
    return tuple(repos)


def describe_watched_github_repositories(topic_slug: str) -> list[dict[str, object]]:
    """Return watched repository metadata for debug visibility."""

    repositories = load_watched_github_repository_entities(topic_slug)
    return [
        {
            "entityId": entity.entity_id,
            "source": entity.source,
            "repo": read_repository_name(entity),
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
            REPOSITORY_RELEASE_CHECKPOINT_KEY,
        )
        checkpoints.append(
            {
                "entityId": entity.entity_id,
                "source": entity.source,
                "repo": read_repository_name(entity),
                "checkpointKey": REPOSITORY_RELEASE_CHECKPOINT_KEY,
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


def resolve_release_checkpoint(
    entity: Entity,
    *,
    baseline_started_after: datetime | None,
) -> datetime | None:
    """Resolve the monitoring cursor for one watched entity."""

    checkpoint = get_entity_checkpoint(
        entity.entity_id,
        REPOSITORY_RELEASE_CHECKPOINT_KEY,
    )
    if checkpoint is not None:
        return datetime.fromisoformat(checkpoint.checkpoint_value).astimezone(UTC)

    return baseline_started_after

"""Tests for entity persistence and topic-specific memory."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entity import Entity, EntityCheckpoint, TopicEntityMatch
from app.storage.entities import (
    get_entity_checkpoint,
    list_entities,
    list_entity_checkpoints,
    list_topic_entity_matches,
    upsert_entities,
    upsert_entity_checkpoints,
    upsert_topic_entity_matches,
)


def test_upsert_entities_persists_global_entities(tmp_path) -> None:
    db_path = tmp_path / "entities.sqlite3"

    upsert_entities(
        [
            Entity(
                entity_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                entity_type="repository",
                canonical_name="Mephistos-ML/paranmr",
                url="https://github.com/Mephistos-ML/paranmr",
                metadata={"stars": 12},
            )
        ],
        db_path=db_path,
    )

    entities = list_entities(source="github", db_path=db_path)

    assert len(entities) == 1
    assert entities[0].entity_id == "github:repo:Mephistos-ML/paranmr"
    assert entities[0].entity_type == "repository"
    assert entities[0].metadata["stars"] == 12


def test_upsert_topic_entity_matches_persists_topic_memory(tmp_path) -> None:
    db_path = tmp_path / "entities.sqlite3"

    upsert_topic_entity_matches(
        [
            TopicEntityMatch(
                topic_slug="pnmr",
                entity_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                score=5.0,
                matched_terms=("paramagnetic nmr", "pcs"),
                reason="Matched core terms in repository description.",
                metadata={"origin": "seed"},
            )
        ],
        db_path=db_path,
    )

    matches = list_topic_entity_matches("pnmr", db_path=db_path)

    assert len(matches) == 1
    assert matches[0].entity_id == "github:repo:Mephistos-ML/paranmr"
    assert matches[0].score == 5.0
    assert matches[0].matched_terms == ("paramagnetic nmr", "pcs")
    assert matches[0].metadata["origin"] == "seed"


def test_upsert_entity_checkpoints_persists_monitoring_cursor(tmp_path) -> None:
    db_path = tmp_path / "entities.sqlite3"
    updated_at = datetime(2026, 7, 18, 9, 30, tzinfo=UTC)

    upsert_entity_checkpoints(
        [
            EntityCheckpoint(
                entity_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                checkpoint_key="latest_release_published_at",
                checkpoint_value="2026-07-18T09:00:00+00:00",
                updated_at=updated_at,
            )
        ],
        db_path=db_path,
    )

    checkpoints = list_entity_checkpoints(
        "github:repo:Mephistos-ML/paranmr",
        db_path=db_path,
    )

    assert len(checkpoints) == 1
    assert checkpoints[0].checkpoint_key == "latest_release_published_at"
    assert checkpoints[0].checkpoint_value == "2026-07-18T09:00:00+00:00"
    assert checkpoints[0].updated_at == updated_at


def test_get_entity_checkpoint_returns_single_cursor(tmp_path) -> None:
    db_path = tmp_path / "entities.sqlite3"
    updated_at = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)

    upsert_entity_checkpoints(
        [
            EntityCheckpoint(
                entity_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                checkpoint_key="latest_release_published_at",
                checkpoint_value="2026-07-18T10:30:00+00:00",
                updated_at=updated_at,
            )
        ],
        db_path=db_path,
    )

    checkpoint = get_entity_checkpoint(
        "github:repo:Mephistos-ML/paranmr",
        "latest_release_published_at",
        db_path=db_path,
    )

    assert checkpoint is not None
    assert checkpoint.checkpoint_value == "2026-07-18T10:30:00+00:00"

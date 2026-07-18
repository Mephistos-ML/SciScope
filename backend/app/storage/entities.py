"""Persistence for watched entities and topic-specific entity memory."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.models.entity import Entity, EntityCheckpoint, TopicEntityMatch
from app.storage.seen_signals import DB_PATH


def init_entity_storage(db_path: Path = DB_PATH) -> None:
    """Initialise entity-related tables."""

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                url TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS topic_entity_matches (
                topic_slug TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                source TEXT NOT NULL,
                score REAL NOT NULL,
                active INTEGER NOT NULL,
                reason TEXT NOT NULL,
                matched_terms_json TEXT NOT NULL,
                excluded_terms_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (topic_slug, entity_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_checkpoints (
                entity_id TEXT NOT NULL,
                source TEXT NOT NULL,
                checkpoint_key TEXT NOT NULL,
                checkpoint_value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (entity_id, checkpoint_key)
            )
            """
        )


def upsert_entities(
    entities: Sequence[Entity],
    db_path: Path = DB_PATH,
) -> None:
    """Insert or update global entities."""

    if not entities:
        return

    init_entity_storage(db_path)
    timestamp = _utc_now_iso()
    rows = [
        (
            entity.entity_id,
            entity.source,
            entity.entity_type,
            entity.canonical_name,
            entity.url,
            json.dumps(entity.metadata, ensure_ascii=False, sort_keys=True),
            timestamp,
            timestamp,
        )
        for entity in entities
    ]

    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO entities (
                entity_id,
                source,
                entity_type,
                canonical_name,
                url,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_id) DO UPDATE SET
                source = excluded.source,
                entity_type = excluded.entity_type,
                canonical_name = excluded.canonical_name,
                url = excluded.url,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            rows,
        )


def list_entities(
    *,
    source: str | None = None,
    entity_type: str | None = None,
    db_path: Path = DB_PATH,
) -> list[Entity]:
    """List global entities with optional source/type filters."""

    init_entity_storage(db_path)

    conditions: list[str] = []
    params: list[object] = []
    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    if entity_type is not None:
        conditions.append("entity_type = ?")
        params.append(entity_type)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT entity_id, source, entity_type, canonical_name, url, metadata_json
        FROM entities
        {where_clause}
        ORDER BY canonical_name ASC
    """

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(query, params).fetchall()

    return [
        Entity(
            entity_id=row[0],
            source=row[1],
            entity_type=row[2],
            canonical_name=row[3],
            url=row[4],
            metadata=_loads_json_dict(row[5]),
        )
        for row in rows
    ]


def list_entities_by_ids(
    entity_ids: Sequence[str],
    *,
    db_path: Path = DB_PATH,
) -> list[Entity]:
    """Load entities by id while preserving the requested subset."""

    if not entity_ids:
        return []

    init_entity_storage(db_path)

    placeholders = ", ".join("?" for _ in entity_ids)
    query = f"""
        SELECT entity_id, source, entity_type, canonical_name, url, metadata_json
        FROM entities
        WHERE entity_id IN ({placeholders})
        ORDER BY canonical_name ASC
    """

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(query, list(entity_ids)).fetchall()

    return [
        Entity(
            entity_id=row[0],
            source=row[1],
            entity_type=row[2],
            canonical_name=row[3],
            url=row[4],
            metadata=_loads_json_dict(row[5]),
        )
        for row in rows
    ]


def upsert_topic_entity_matches(
    matches: Sequence[TopicEntityMatch],
    db_path: Path = DB_PATH,
) -> None:
    """Insert or update topic-to-entity relevance matches."""

    if not matches:
        return

    init_entity_storage(db_path)
    timestamp = _utc_now_iso()
    rows = [
        (
            match.topic_slug,
            match.entity_id,
            match.source,
            match.score,
            int(match.active),
            match.reason,
            json.dumps(match.matched_terms, ensure_ascii=False),
            json.dumps(match.excluded_terms, ensure_ascii=False),
            json.dumps(match.metadata, ensure_ascii=False, sort_keys=True),
            timestamp,
            timestamp,
        )
        for match in matches
    ]

    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO topic_entity_matches (
                topic_slug,
                entity_id,
                source,
                score,
                active,
                reason,
                matched_terms_json,
                excluded_terms_json,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic_slug, entity_id) DO UPDATE SET
                source = excluded.source,
                score = excluded.score,
                active = excluded.active,
                reason = excluded.reason,
                matched_terms_json = excluded.matched_terms_json,
                excluded_terms_json = excluded.excluded_terms_json,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            rows,
        )


def list_topic_entity_matches(
    topic_slug: str,
    *,
    active_only: bool = True,
    db_path: Path = DB_PATH,
) -> list[TopicEntityMatch]:
    """List entity matches for one topic."""

    init_entity_storage(db_path)

    query = """
        SELECT
            topic_slug,
            entity_id,
            source,
            score,
            active,
            reason,
            matched_terms_json,
            excluded_terms_json,
            metadata_json
        FROM topic_entity_matches
        WHERE topic_slug = ?
    """
    params: list[object] = [topic_slug]
    if active_only:
        query += " AND active = 1"
    query += " ORDER BY score DESC, entity_id ASC"

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(query, params).fetchall()

    return [
        TopicEntityMatch(
            topic_slug=row[0],
            entity_id=row[1],
            source=row[2],
            score=float(row[3]),
            active=bool(row[4]),
            reason=row[5],
            matched_terms=tuple(_loads_json_list(row[6])),
            excluded_terms=tuple(_loads_json_list(row[7])),
            metadata=_loads_json_dict(row[8]),
        )
        for row in rows
    ]


def upsert_entity_checkpoints(
    checkpoints: Sequence[EntityCheckpoint],
    db_path: Path = DB_PATH,
) -> None:
    """Insert or update monitoring checkpoints for entities."""

    if not checkpoints:
        return

    init_entity_storage(db_path)
    rows = [
        (
            checkpoint.entity_id,
            checkpoint.source,
            checkpoint.checkpoint_key,
            checkpoint.checkpoint_value,
            checkpoint.updated_at.astimezone(UTC).isoformat(),
        )
        for checkpoint in checkpoints
    ]

    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO entity_checkpoints (
                entity_id,
                source,
                checkpoint_key,
                checkpoint_value,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entity_id, checkpoint_key) DO UPDATE SET
                source = excluded.source,
                checkpoint_value = excluded.checkpoint_value,
                updated_at = excluded.updated_at
            """,
            rows,
        )


def list_entity_checkpoints(
    entity_id: str,
    *,
    db_path: Path = DB_PATH,
) -> list[EntityCheckpoint]:
    """List checkpoints for one entity."""

    init_entity_storage(db_path)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT entity_id, source, checkpoint_key, checkpoint_value, updated_at
            FROM entity_checkpoints
            WHERE entity_id = ?
            ORDER BY checkpoint_key ASC
            """,
            (entity_id,),
        ).fetchall()

    return [
        EntityCheckpoint(
            entity_id=row[0],
            source=row[1],
            checkpoint_key=row[2],
            checkpoint_value=row[3],
            updated_at=datetime.fromisoformat(row[4]),
        )
        for row in rows
    ]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _loads_json_dict(raw: str) -> dict[str, object]:
    value = json.loads(raw)
    if isinstance(value, dict):
        return value
    return {}


def _loads_json_list(raw: str) -> list[str]:
    value = json.loads(raw)
    if isinstance(value, list):
        return [str(item) for item in value]
    return []

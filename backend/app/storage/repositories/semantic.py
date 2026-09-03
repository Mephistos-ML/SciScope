"""Postgres pgvector persistence and lookup for catalog semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from sqlalchemy import text

from app.database.session import get_engine, session_scope


def semantic_catalog_is_available(*, database_url: str) -> bool:
    """Return whether this database can execute pgvector retrieval."""

    return get_engine(database_url).dialect.name == "postgresql"


def filter_missing_query_embeddings(
    inputs: Mapping[str, str],
    *,
    embedding_model: str,
    database_url: str,
) -> dict[str, str]:
    return _filter_missing(
        "repository_query_embeddings",
        "query_normalized",
        inputs,
        embedding_model=embedding_model,
        database_url=database_url,
    )


def filter_missing_profile_embeddings(
    inputs: Mapping[str, str],
    *,
    embedding_model: str,
    database_url: str,
) -> dict[str, str]:
    return _filter_missing(
        "repository_profile_embeddings",
        "repository_id",
        inputs,
        embedding_model=embedding_model,
        database_url=database_url,
    )


def upsert_query_embeddings(
    embeddings: Mapping[str, tuple[str, Sequence[float]]],
    *,
    embedding_model: str,
    database_url: str,
) -> None:
    _upsert_embeddings(
        "repository_query_embeddings",
        "query_normalized",
        embeddings,
        embedding_model=embedding_model,
        database_url=database_url,
    )


def upsert_profile_embeddings(
    embeddings: Mapping[str, tuple[str, Sequence[float]]],
    *,
    embedding_model: str,
    database_url: str,
) -> None:
    _upsert_embeddings(
        "repository_profile_embeddings",
        "repository_id",
        embeddings,
        embedding_model=embedding_model,
        database_url=database_url,
    )


def find_semantic_query_evidence(
    embedding: Sequence[float],
    *,
    embedding_model: str,
    limit: int,
    min_similarity: float,
    database_url: str,
) -> list[dict[str, object]]:
    """Find stored query evidence nearest to one current query embedding."""

    if not semantic_catalog_is_available(database_url=database_url):
        return []
    vector = _vector_literal(embedding)
    statement = text(
        """
        SELECT evidence.repository_id, evidence.query_normalized, evidence.channel,
               evidence.match_location, evidence.matched_path, evidence.provider_rank,
               evidence.hit_count,
               1 - (query_embedding.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM repository_query_embeddings AS query_embedding
        JOIN repository_query_evidence AS evidence
          ON evidence.query_normalized = query_embedding.query_normalized
        WHERE query_embedding.embedding_model = :embedding_model
          AND 1 - (query_embedding.embedding <=> CAST(:embedding AS vector)) >= :min_similarity
        ORDER BY query_embedding.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )
    with session_scope(database_url) as session:
        rows = session.execute(
            statement,
            {
                "embedding": vector,
                "embedding_model": embedding_model,
                "min_similarity": min_similarity,
                "limit": limit,
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def find_semantic_profiles(
    embedding: Sequence[float],
    *,
    embedding_model: str,
    limit: int,
    min_similarity: float,
    database_url: str,
) -> list[dict[str, object]]:
    """Find repository profiles nearest to one current query embedding."""

    if not semantic_catalog_is_available(database_url=database_url):
        return []
    vector = _vector_literal(embedding)
    statement = text(
        """
        SELECT repository_id,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM repository_profile_embeddings
        WHERE embedding_model = :embedding_model
          AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_similarity
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )
    with session_scope(database_url) as session:
        rows = session.execute(
            statement,
            {
                "embedding": vector,
                "embedding_model": embedding_model,
                "min_similarity": min_similarity,
                "limit": limit,
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def _filter_missing(
    table_name: str,
    key_column: str,
    inputs: Mapping[str, str],
    *,
    embedding_model: str,
    database_url: str,
) -> dict[str, str]:
    if not inputs or not semantic_catalog_is_available(database_url=database_url):
        return {}
    hashes = {key: _content_hash(content) for key, content in inputs.items()}
    statement = text(
        f"SELECT {key_column}, content_hash FROM {table_name} "
        f"WHERE {key_column} = ANY(:keys) AND embedding_model = :embedding_model"
    )
    with session_scope(database_url) as session:
        existing = {
            str(row[0]): str(row[1])
            for row in session.execute(
                statement,
                {"keys": list(inputs), "embedding_model": embedding_model},
            )
        }
    return {
        key: content
        for key, content in inputs.items()
        if existing.get(key) != hashes[key]
    }


def _upsert_embeddings(
    table_name: str,
    key_column: str,
    embeddings: Mapping[str, tuple[str, Sequence[float]]],
    *,
    embedding_model: str,
    database_url: str,
) -> None:
    if not embeddings or not semantic_catalog_is_available(database_url=database_url):
        return
    now = datetime.now(UTC)
    statement = text(
        f"""
        INSERT INTO {table_name} ({key_column}, embedding, embedding_model, content_hash, created_at, updated_at)
        VALUES (:{key_column}, CAST(:embedding AS vector), :embedding_model, :content_hash, :created_at, :updated_at)
        ON CONFLICT ({key_column}) DO UPDATE SET
          embedding = EXCLUDED.embedding,
          embedding_model = EXCLUDED.embedding_model,
          content_hash = EXCLUDED.content_hash,
          updated_at = EXCLUDED.updated_at
        """
    )
    rows = [
        {
            key_column: key,
            "embedding": _vector_literal(vector),
            "embedding_model": embedding_model,
            "content_hash": content_hash,
            "created_at": now,
            "updated_at": now,
        }
        for key, (content_hash, vector) in embeddings.items()
    ]
    with session_scope(database_url) as session:
        session.execute(statement, rows)


def _content_hash(content: str) -> str:
    from hashlib import sha256

    return sha256(content.encode("utf-8")).hexdigest()


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(format(value, ".8g") for value in vector) + "]"

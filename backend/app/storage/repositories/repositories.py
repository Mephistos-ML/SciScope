"""Persistence helpers for repository records."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import exists, func, or_, select

from app.database.records import (
    RepositoryRecordModel,
    RepositorySearchEvidenceRecordModel,
)
from app.database.session import get_engine, session_scope
from app.models.repository import (
    CatalogRepositoryMatch,
    Repository,
    RepositorySearchEvidence,
    parse_repository_id,
)


def upsert_repositories(
    repositories: Sequence[Repository],
    *,
    database_url: str,
) -> None:
    """Insert or update global repository catalog profiles."""

    if not repositories:
        return

    timestamp = _utc_now()
    with session_scope(database_url) as session:
        for repository in repositories:
            record = session.get(RepositoryRecordModel, repository.repository_id)
            provider_repository_id = repository.provider_repository_id.strip() or parse_repository_id(
                repository.repository_id,
                source=repository.source,
            )
            search_text = _build_search_text(repository)
            if record is None:
                session.add(
                    RepositoryRecordModel(
                        repository_id=repository.repository_id,
                        source=repository.source,
                        full_name=repository.full_name,
                        url=repository.url,
                        provider_repository_id=provider_repository_id,
                        owner_login=repository.owner_login,
                        description=repository.description,
                        language=repository.language,
                        stars=repository.stars,
                        topics_json=list(repository.topics),
                        search_text=search_text,
                        first_seen_at=repository.first_seen_at or timestamp,
                        last_seen_at=repository.last_seen_at or timestamp,
                        last_retrieved_at=repository.last_retrieved_at or timestamp,
                        provider_updated_at=repository.provider_updated_at,
                        metadata_json=dict(repository.metadata),
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                continue

            record.source = repository.source
            record.full_name = repository.full_name
            record.url = repository.url
            record.provider_repository_id = provider_repository_id
            record.owner_login = repository.owner_login
            record.description = repository.description
            record.language = repository.language
            record.stars = repository.stars
            record.topics_json = list(repository.topics)
            record.search_text = search_text
            record.last_seen_at = repository.last_seen_at or timestamp
            record.last_retrieved_at = repository.last_retrieved_at or timestamp
            record.provider_updated_at = repository.provider_updated_at
            record.metadata_json = dict(repository.metadata)
            record.updated_at = timestamp


def upsert_repository_search_evidence(
    evidence_items: Sequence[RepositorySearchEvidence],
    *,
    database_url: str,
) -> None:
    """Persist idempotent query-to-repository retrieval evidence."""

    if not evidence_items:
        return

    timestamp = _utc_now()
    with session_scope(database_url) as session:
        for evidence in evidence_items:
            key = (
                evidence.repository_id,
                evidence.query_normalized,
                evidence.channel,
                evidence.match_location,
                evidence.matched_path,
            )
            record = session.get(RepositorySearchEvidenceRecordModel, key)
            if record is None:
                session.add(
                    RepositorySearchEvidenceRecordModel(
                        repository_id=evidence.repository_id,
                        query_normalized=evidence.query_normalized,
                        channel=evidence.channel,
                        match_location=evidence.match_location,
                        matched_path=evidence.matched_path,
                        matched_excerpt=evidence.matched_excerpt,
                        provider_rank=evidence.provider_rank,
                        hit_count=max(1, evidence.hit_count),
                        first_seen_at=evidence.first_seen_at or timestamp,
                        last_seen_at=evidence.last_seen_at or timestamp,
                    )
                )
                continue

            record.matched_excerpt = evidence.matched_excerpt or record.matched_excerpt
            record.provider_rank = _best_rank(record.provider_rank, evidence.provider_rank)
            record.hit_count += max(1, evidence.hit_count)
            record.last_seen_at = evidence.last_seen_at or timestamp


def find_catalog_repository_matches(
    queries: Sequence[str],
    *,
    limit: int = 100,
    database_url: str,
) -> list[CatalogRepositoryMatch]:
    """Return catalog repositories with profile or evidence overlap for a query plan."""

    normalized_queries = _normalize_queries(queries)
    if not normalized_queries:
        return []

    if get_engine(database_url).dialect.name == "postgresql":
        profile_conditions = [
            func.to_tsvector("simple", RepositoryRecordModel.search_text).op("@@")(
                func.plainto_tsquery("simple", query)
            )
            for query in normalized_queries
        ]
    else:
        profile_conditions = [
            func.lower(RepositoryRecordModel.search_text).like(f"%{query}%")
            for query in normalized_queries
        ]
    evidence_conditions = [
        func.lower(RepositorySearchEvidenceRecordModel.query_normalized).like(
            f"%{query}%"
        )
        for query in normalized_queries
    ]
    evidence_matches = exists(
        select(1)
        .select_from(RepositorySearchEvidenceRecordModel)
        .where(
            RepositorySearchEvidenceRecordModel.repository_id
            == RepositoryRecordModel.repository_id
        )
        .where(or_(*evidence_conditions))
    )
    statement = (
        select(RepositoryRecordModel)
        .where(or_(*profile_conditions, evidence_matches))
        .order_by(RepositoryRecordModel.stars.desc(), RepositoryRecordModel.full_name.asc())
        .limit(limit)
    )
    with session_scope(database_url) as session:
        repository_rows = session.scalars(statement).all()
        repository_ids = [row.repository_id for row in repository_rows]
        evidence_rows = (
            session.scalars(
                select(RepositorySearchEvidenceRecordModel).where(
                    RepositorySearchEvidenceRecordModel.repository_id.in_(repository_ids)
                )
            ).all()
            if repository_ids
            else []
        )

    evidence_by_repository: dict[str, list[RepositorySearchEvidence]] = {}
    for row in evidence_rows:
        evidence_by_repository.setdefault(row.repository_id, []).append(_to_evidence(row))

    matches: list[CatalogRepositoryMatch] = []
    for row in repository_rows:
        repository = _to_repository(row)
        evidence = tuple(evidence_by_repository.get(repository.repository_id, []))
        matched_queries = tuple(
            query
            for query in normalized_queries
            if _query_matches(_build_search_text(repository), query)
            or any(_query_matches(item.query_normalized, query) for item in evidence)
        )
        if matched_queries:
            matches.append(
                CatalogRepositoryMatch(
                    repository=repository,
                    matched_queries=matched_queries,
                    evidence=tuple(
                        item
                        for item in evidence
                        if any(
                            _query_matches(item.query_normalized, query)
                            for query in matched_queries
                        )
                    ),
                )
            )
    return matches


def list_repositories(
    *,
    source: str | None = None,
    database_url: str,
) -> list[Repository]:
    """List repositories with an optional source filter."""

    statement = select(RepositoryRecordModel)
    if source is not None:
        statement = statement.where(RepositoryRecordModel.source == source)
    statement = statement.order_by(RepositoryRecordModel.full_name.asc())

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository(row) for row in rows]


def list_repositories_by_ids(
    repository_ids: Sequence[str],
    *,
    database_url: str,
) -> list[Repository]:
    """Load repositories by id while preserving the requested subset."""

    if not repository_ids:
        return []

    statement = (
        select(RepositoryRecordModel)
        .where(RepositoryRecordModel.repository_id.in_(tuple(repository_ids)))
        .order_by(RepositoryRecordModel.full_name.asc())
    )

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository(row) for row in rows]


def list_repository_search_evidence(
    *,
    database_url: str,
) -> list[RepositorySearchEvidence]:
    """Return catalog query evidence for an administrative semantic backfill."""

    statement = select(RepositorySearchEvidenceRecordModel).order_by(
        RepositorySearchEvidenceRecordModel.query_normalized.asc()
    )
    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_evidence(row) for row in rows]


def get_repository(
    repository_id: str,
    *,
    database_url: str,
) -> Repository | None:
    """Load one repository by id."""

    with session_scope(database_url) as session:
        row = session.get(RepositoryRecordModel, repository_id)
    if row is None:
        return None
    return _to_repository(row)


def _to_repository(record: RepositoryRecordModel) -> Repository:
    return Repository(
        repository_id=record.repository_id,
        source=record.source,
        full_name=record.full_name,
        url=record.url,
        metadata=dict(record.metadata_json or {}),
        provider_repository_id=record.provider_repository_id,
        owner_login=record.owner_login,
        description=record.description,
        language=record.language,
        stars=record.stars,
        topics=tuple(record.topics_json or []),
        first_seen_at=_ensure_utc(record.first_seen_at),
        last_seen_at=_ensure_utc(record.last_seen_at),
        last_retrieved_at=_ensure_utc(record.last_retrieved_at),
        provider_updated_at=(
            _ensure_utc(record.provider_updated_at)
            if record.provider_updated_at is not None
            else None
        ),
    )


def _to_evidence(record: RepositorySearchEvidenceRecordModel) -> RepositorySearchEvidence:
    return RepositorySearchEvidence(
        repository_id=record.repository_id,
        query_normalized=record.query_normalized,
        channel=record.channel,
        match_location=record.match_location,
        matched_path=record.matched_path,
        matched_excerpt=record.matched_excerpt,
        provider_rank=record.provider_rank,
        hit_count=record.hit_count,
        first_seen_at=_ensure_utc(record.first_seen_at),
        last_seen_at=_ensure_utc(record.last_seen_at),
    )


def _build_search_text(repository: Repository) -> str:
    return "\n".join(
        value.strip()
        for value in (
            repository.full_name,
            repository.description,
            " ".join(repository.topics),
            repository.language,
        )
        if value.strip()
    )


def _normalize_queries(queries: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            " ".join(query.casefold().split())
            for query in queries
            if " ".join(query.split())
        )
    )


def _query_matches(text: str, query: str) -> bool:
    normalized_text = " ".join(text.casefold().split())
    return query in normalized_text or set(query.split()).issubset(set(normalized_text.split()))


def _best_rank(current: int | None, incoming: int | None) -> int | None:
    if current is None:
        return incoming
    if incoming is None:
        return current
    return min(current, incoming)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

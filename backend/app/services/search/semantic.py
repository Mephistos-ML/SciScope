"""Semantic catalog ingestion and pgvector-backed candidate retrieval."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import logging
from app.models.persistence import PersistenceUnavailableError, PersistenceConflictError

from app import config
from app.services.ai.embeddings import EmbeddingProvider
from app.models.ai import AiDependencyError
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.search.retrieval import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalMatchEvidence,
)
from app.storage.repositories import (
    filter_missing_profile_embeddings,
    filter_missing_query_embeddings,
    find_semantic_profiles,
    find_semantic_query_evidence,
    list_repositories_by_ids,
    list_repositories,
    list_repository_search_evidence,
    semantic_catalog_is_available,
    upsert_profile_embeddings,
    upsert_query_embeddings,
)

logger = logging.getLogger(__name__)


def persist_semantic_catalog_documents(
    repositories: Sequence[Repository],
    queries: Sequence[str],
    *,
    database_url: str,
    embeddings: EmbeddingProvider | None,
    raise_on_error: bool = False,
) -> None:
    """Embed changed catalog documents after their canonical records are persisted."""

    if embeddings is None:
        return
    if not semantic_catalog_is_available(database_url=database_url):
        return
    query_documents = {
        normalized: normalized
        for query in queries
        if (normalized := _normalize(query))
    }
    profile_documents = {
        repository.repository_id: _profile_text(repository)
        for repository in repositories
        if _profile_text(repository)
    }
    try:
        _persist_documents(
            query_documents,
            filter_missing=filter_missing_query_embeddings,
            upsert=upsert_query_embeddings,
            database_url=database_url,
            embeddings=embeddings,
        )
        _persist_documents(
            profile_documents,
            filter_missing=filter_missing_profile_embeddings,
            upsert=upsert_profile_embeddings,
            database_url=database_url,
            embeddings=embeddings,
        )
    except (PersistenceUnavailableError, PersistenceConflictError, AiDependencyError):
        logger.exception("Semantic catalog ingestion failed without affecting search.")
        if raise_on_error:
            raise


def backfill_semantic_catalog(*, database_url: str, embeddings: EmbeddingProvider) -> tuple[int, int]:
    """Embed existing canonical catalog records once after enabling pgvector."""

    repositories = list_repositories(database_url=database_url)
    evidence = list_repository_search_evidence(database_url=database_url)
    persist_semantic_catalog_documents(
        repositories,
        tuple(item.query_normalized for item in evidence),
        database_url=database_url,
        embeddings=embeddings,
        raise_on_error=True,
    )
    return len(repositories), len({item.query_normalized for item in evidence})


def retrieve_semantic_catalog_candidates(
    queries: Sequence[str],
    *,
    database_url: str,
    embeddings: EmbeddingProvider | None,
) -> tuple[RepositoryCandidate, ...]:
    """Retrieve catalog candidates by query and profile semantic similarity."""

    if embeddings is None or not semantic_catalog_is_available(database_url=database_url):
        return ()
    normalized_queries = tuple(dict.fromkeys(_normalize(query) for query in queries if _normalize(query)))
    if not normalized_queries:
        return ()
    try:
        vectors = embeddings.embed(normalized_queries)
        evidence_by_repository: dict[str, list[RetrievalMatchEvidence]] = defaultdict(list)
        matched_queries_by_repository: dict[str, list[str]] = defaultdict(list)
        for query, embedding in zip(normalized_queries, vectors, strict=True):
            for retrieval_rank, row in enumerate(
                find_semantic_query_evidence(
                    embedding,
                    embedding_model=embeddings.model,
                    limit=config.SEMANTIC_CATALOG_QUERY_LIMIT,
                    min_similarity=config.SEMANTIC_CATALOG_MIN_SIMILARITY,
                    database_url=database_url,
                ),
                start=1,
            ):
                repository_id = str(row["repository_id"])
                _append_match(
                    evidence_by_repository,
                    matched_queries_by_repository,
                    repository_id=repository_id,
                    query=query,
                    location=str(row["match_location"]),
                    path=str(row["matched_path"] or ""),
                    similarity=float(row["similarity"]),
                    retrieval_rank=retrieval_rank,
                )
            for retrieval_rank, row in enumerate(
                find_semantic_profiles(
                    embedding,
                    embedding_model=embeddings.model,
                    limit=config.SEMANTIC_CATALOG_PROFILE_LIMIT,
                    min_similarity=config.SEMANTIC_CATALOG_MIN_SIMILARITY,
                    database_url=database_url,
                ),
                start=1,
            ):
                repository_id = str(row["repository_id"])
                _append_match(
                    evidence_by_repository,
                    matched_queries_by_repository,
                    repository_id=repository_id,
                    query=query,
                    location="metadata",
                    path="",
                    similarity=float(row["similarity"]),
                    retrieval_rank=retrieval_rank,
                )
        repositories = list_repositories_by_ids(
            tuple(evidence_by_repository),
            database_url=database_url,
        )
    except (PersistenceUnavailableError, PersistenceConflictError, AiDependencyError):
        logger.exception("Semantic catalog retrieval failed; using lexical retrieval only.")
        return ()

    return tuple(
        _build_candidate(
            repository,
            matched_queries=tuple(matched_queries_by_repository[repository.repository_id]),
            evidence=tuple(evidence_by_repository[repository.repository_id]),
        )
        for repository in repositories
    )


def _persist_documents(
    documents: Mapping[str, str],
    *,
    filter_missing: Callable[..., Mapping[str, str]],
    upsert: Callable[..., None],
    database_url: str,
    embeddings: EmbeddingProvider,
) -> None:
    missing = filter_missing(
        documents,
        embedding_model=embeddings.model,
        database_url=database_url,
    )
    if not missing:
        return
    payload: dict[str, tuple[str, tuple[float, ...]]] = {}
    for batch in _document_batches(missing):
        try:
            vectors = embeddings.embed(tuple(content for _, content in batch))
        except AiDependencyError as exc:
            sample_keys = ", ".join(key for key, _ in batch[:3])
            raise AiDependencyError(
                "Embedding batch failed for "
                f"{len(batch)} documents (sample keys: {sample_keys})."
            ) from exc
        payload.update(
            {
                key: (_content_hash(content), vector)
                for (key, content), vector in zip(batch, vectors, strict=True)
            }
        )
    upsert(
        payload,
        embedding_model=embeddings.model,
        database_url=database_url,
    )


def _build_candidate(
    repository: Repository,
    *,
    matched_queries: tuple[str, ...],
    evidence: tuple[RetrievalMatchEvidence, ...],
) -> RepositoryCandidate:
    return RepositoryCandidate(
        repository_id=repository.repository_id,
        signal=Signal(
            source=repository.source,
            kind="repository",
            item_id=repository.repository_id,
            title=repository.full_name,
            url=repository.url,
            published_at=None,
            raw_text=_profile_text(repository),
            payload={
                "repo": repository.full_name,
                "provider_repository_id": repository.provider_repository_id,
                "author": repository.owner_login,
                "description": repository.description,
                "topics": list(repository.topics),
                "language": repository.language,
                "stars": repository.stars,
                "provider_updated_at": (
                    repository.provider_updated_at.isoformat()
                    if repository.provider_updated_at is not None
                    else None
                ),
                "query": matched_queries[0] if matched_queries else None,
            },
        ),
        provenance=CandidateProvenance(
            matched_queries=matched_queries,
            matched_channels=("semantic_catalog",),
            best_rank_by_channel={
                "semantic_catalog": min(
                    (
                        item.retrieval_rank
                        for item in evidence
                        if item.retrieval_rank is not None
                    ),
                    default=1,
                )
            },
            hit_count=len(evidence),
            match_evidence=evidence,
            origins=("catalog",),
        ),
    )


def _append_match(
    evidence_by_repository: dict[str, list[RetrievalMatchEvidence]],
    queries_by_repository: dict[str, list[str]],
    *,
    repository_id: str,
    query: str,
    location: str,
    path: str,
    similarity: float,
    retrieval_rank: int,
) -> None:
    bounded_similarity = min(1.0, max(0.0, similarity))
    if query not in queries_by_repository[repository_id]:
        queries_by_repository[repository_id].append(query)
    item = RetrievalMatchEvidence(
        query=query,
        location=location,  # type: ignore[arg-type]
        path=path,
        alignment=bounded_similarity,
        channel="semantic_catalog",
        origin="catalog",
        retrieval_rank=retrieval_rank,
    )
    if item not in evidence_by_repository[repository_id]:
        evidence_by_repository[repository_id].append(item)


def _normalize(query: str) -> str:
    return " ".join(query.casefold().split())


def _profile_text(repository: Repository) -> str:
    text = "\n".join(
        value.strip()
        for value in (
            repository.full_name,
            repository.description,
            " ".join(repository.topics),
        )
        if value.strip()
    )
    return text[: config.SEMANTIC_EMBEDDING_MAX_INPUT_CHARS]


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _document_batches(
    documents: Mapping[str, str],
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Keep embedding requests bounded by both item count and input size."""

    batches: list[tuple[tuple[str, str], ...]] = []
    current: list[tuple[str, str]] = []
    current_chars = 0
    for key, content in documents.items():
        if current and (
            len(current) >= config.SEMANTIC_EMBEDDING_BATCH_SIZE
            or current_chars + len(content) > config.SEMANTIC_EMBEDDING_BATCH_MAX_CHARS
        ):
            batches.append(tuple(current))
            current = []
            current_chars = 0
        current.append((key, content))
        current_chars += len(content)
    if current:
        batches.append(tuple(current))
    return tuple(batches)

"""Catalog retrieval and ingestion for the Explore use case."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import logging

from sqlalchemy.exc import DBAPIError

from app.models.repository import Repository, RepositorySearchEvidence
from app.models.signal import Signal
from app.services.search.retrieval import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalMatchEvidence,
)
from app.storage.repositories import (
    find_catalog_repository_matches,
    upsert_repositories,
    upsert_repository_search_evidence,
)

logger = logging.getLogger(__name__)


def retrieve_catalog_candidates(
    queries: Sequence[str],
    *,
    database_url: str,
) -> tuple[RepositoryCandidate, ...]:
    """Map locally indexed catalog records into the standard retrieval contract."""

    candidates: list[RepositoryCandidate] = []
    try:
        matches = find_catalog_repository_matches(queries, database_url=database_url)
    except DBAPIError:
        logger.exception("Catalog retrieval failed; falling back to external providers.")
        return ()

    for match in matches:
        repository = match.repository
        signal = Signal(
            source=repository.source,
            kind="repository",
            item_id=repository.repository_id,
            title=repository.full_name,
            url=repository.url,
            published_at=None,
            raw_text=_build_search_text(repository),
            payload={
                "repo": repository.full_name,
                "provider_repository_id": repository.provider_repository_id,
                "author": repository.owner_login,
                "description": repository.description,
                "topics": list(repository.topics),
                "language": repository.language,
                "stars": repository.stars,
            },
        )
        evidence = tuple(
            RetrievalMatchEvidence(
                query=next(
                    (
                        query
                        for query in match.matched_queries
                        if _query_matches(item.query_normalized, query)
                    ),
                    item.query_normalized,
                ),
                location=item.match_location,  # type: ignore[arg-type]
                path=item.matched_path,
            )
            for item in match.evidence
        )
        if not evidence:
            evidence = tuple(
                RetrievalMatchEvidence(
                    query=query,
                    location="metadata",
                )
                for query in match.matched_queries
            )
        matched_channels = tuple(dict.fromkeys(item.channel for item in match.evidence))
        if not matched_channels:
            matched_channels = ("catalog",)
        best_rank_by_channel = {
            channel: min(
                (
                    item.provider_rank
                    for item in match.evidence
                    if item.channel == channel and item.provider_rank is not None
                ),
                default=1,
            )
            for channel in matched_channels
        }
        candidates.append(
            RepositoryCandidate(
                repository_id=repository.repository_id,
                signal=signal,
                provenance=CandidateProvenance(
                    matched_queries=match.matched_queries,
                    matched_channels=matched_channels,
                    best_rank_by_channel=best_rank_by_channel,
                    hit_count=max(1, sum(item.hit_count for item in match.evidence)),
                    match_evidence=evidence,
                    origins=("catalog",),
                ),
            )
        )
    return tuple(candidates)


def persist_catalog_candidates(
    candidates: Sequence[RepositoryCandidate],
    *,
    database_url: str,
) -> None:
    """Persist admitted external candidates and their retrieval evidence."""

    if not candidates:
        return

    now = datetime.now(UTC)
    repositories = tuple(_build_repository(candidate, now=now) for candidate in candidates)
    evidence = tuple(
        item
        for candidate in candidates
        for item in _build_evidence(candidate, now=now)
    )
    try:
        upsert_repositories(repositories, database_url=database_url)
        upsert_repository_search_evidence(evidence, database_url=database_url)
    except DBAPIError:
        logger.exception("Catalog ingestion failed after external retrieval.")


def _build_repository(candidate: RepositoryCandidate, *, now: datetime) -> Repository:
    signal = candidate.signal
    payload = signal.payload
    topics = payload.get("topics")
    return Repository(
        repository_id=candidate.repository_id,
        source=signal.source,
        full_name=str(payload.get("repo") or signal.title),
        url=signal.url,
        metadata={},
        provider_repository_id=str(payload.get("provider_repository_id") or ""),
        owner_login=str(payload.get("author") or ""),
        description=str(payload.get("description") or ""),
        language=str(payload.get("language") or ""),
        stars=int(payload.get("stars") or 0),
        topics=tuple(str(topic) for topic in topics if str(topic).strip()) if isinstance(topics, list) else (),
        first_seen_at=now,
        last_seen_at=now,
        last_retrieved_at=now,
    )


def _build_evidence(
    candidate: RepositoryCandidate,
    *,
    now: datetime,
) -> tuple[RepositorySearchEvidence, ...]:
    channels = candidate.provenance.matched_channels or ("repository_search",)
    default_channel = channels[0]
    evidence_items: list[RepositorySearchEvidence] = []
    for item in candidate.provenance.match_evidence:
        channel = _channel_for_location(item, channels, default_channel)
        evidence_items.append(
            RepositorySearchEvidence(
                repository_id=candidate.repository_id,
                query_normalized=_normalize_query(item.query),
                channel=channel,
                match_location=item.location,
                matched_path=item.path,
                matched_excerpt=str(candidate.signal.payload.get("matched_excerpt") or ""),
                provider_rank=candidate.provenance.best_rank_by_channel.get(channel),
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    return tuple(evidence_items)


def _channel_for_location(
    evidence: RetrievalMatchEvidence,
    channels: tuple[str, ...],
    default_channel: str,
) -> str:
    if evidence.location in {"code", "readme", "documentation", "other"}:
        return next((channel for channel in channels if channel == "code_search"), default_channel)
    return next((channel for channel in channels if channel == "repository_search"), default_channel)


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


def _normalize_query(query: str) -> str:
    return " ".join(query.casefold().split())


def _query_matches(text: str, query: str) -> bool:
    normalized_text = _normalize_query(text)
    normalized_query = _normalize_query(query)
    return (
        normalized_query in normalized_text
        or set(normalized_query.split()).issubset(set(normalized_text.split()))
    )

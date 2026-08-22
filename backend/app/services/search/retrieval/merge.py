"""Merge helpers for deduplicated repository candidate pools."""

from __future__ import annotations

from app.models.signal import Signal
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalHit,
)


def merge_retrieval_hits(hits: tuple[RetrievalHit, ...]) -> tuple[RepositoryCandidate, ...]:
    """Merge raw retrieval hits into one deduplicated candidate pool."""

    merged: dict[str, RepositoryCandidate] = {}

    for hit in hits:
        repository_id = hit.signal.item_id
        existing = merged.get(repository_id)
        if existing is None:
            merged[repository_id] = RepositoryCandidate(
                repository_id=repository_id,
                signal=hit.signal,
                provenance=CandidateProvenance(
                    matched_queries=(hit.query,),
                    matched_channels=(hit.channel,),
                    best_rank_by_channel={hit.channel: hit.rank},
                    hit_count=1,
                ),
            )
            continue

        merged[repository_id] = RepositoryCandidate(
            repository_id=repository_id,
            signal=_select_preferred_signal(existing.signal, hit.signal),
            provenance=_merge_provenance(existing.provenance, hit),
        )

    return tuple(merged.values())


def _merge_provenance(
    existing: CandidateProvenance,
    incoming: RetrievalHit,
) -> CandidateProvenance:
    matched_queries = _append_unique(existing.matched_queries, incoming.query)
    matched_channels = _append_unique(existing.matched_channels, incoming.channel)
    best_rank_by_channel = dict(existing.best_rank_by_channel)
    current_best_rank = best_rank_by_channel.get(incoming.channel)
    if current_best_rank is None or incoming.rank < current_best_rank:
        best_rank_by_channel[incoming.channel] = incoming.rank

    return CandidateProvenance(
        matched_queries=matched_queries,
        matched_channels=matched_channels,
        best_rank_by_channel=best_rank_by_channel,
        hit_count=existing.hit_count + 1,
    )


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    if value in values:
        return values
    return (*values, value)


def _select_preferred_signal(existing: Signal, incoming: Signal) -> Signal:
    existing_query = str(existing.payload.get("query") or "")
    incoming_query = str(incoming.payload.get("query") or "")
    if len(incoming_query) > len(existing_query):
        return incoming
    return existing

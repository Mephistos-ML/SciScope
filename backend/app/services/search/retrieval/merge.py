"""Merge helpers for deduplicated repository candidate pools."""

from __future__ import annotations

from app.models.signal import Signal
from app.services.search.retrieval.evidence import build_retrieval_match_evidence
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalHit,
    RetrievalMatchEvidence,
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
                    match_evidence=(build_retrieval_match_evidence(hit),),
                ),
            )
            continue

        merged[repository_id] = RepositoryCandidate(
            repository_id=repository_id,
            signal=_merge_signals(existing.signal, hit.signal),
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
        match_evidence=_append_unique_evidence(
            existing.match_evidence,
            build_retrieval_match_evidence(incoming),
        ),
    )


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    if value in values:
        return values
    return (*values, value)


def _append_unique_evidence(
    existing: tuple[RetrievalMatchEvidence, ...],
    incoming: RetrievalMatchEvidence,
) -> tuple[RetrievalMatchEvidence, ...]:
    if incoming in existing:
        return existing
    return (*existing, incoming)


def _select_preferred_signal(existing: Signal, incoming: Signal) -> Signal:
    existing_query = str(existing.payload.get("query") or "")
    incoming_query = str(incoming.payload.get("query") or "")
    if len(incoming_query) > len(existing_query):
        return incoming
    return existing


def _merge_signals(existing: Signal, incoming: Signal) -> Signal:
    preferred = _select_preferred_signal(existing, incoming)
    secondary = incoming if preferred is existing else existing
    merged_payload = dict(secondary.payload)
    merged_payload.update(preferred.payload)

    merged_topics = _merge_topics(
        secondary.payload.get("topics"),
        preferred.payload.get("topics"),
    )
    if merged_topics:
        merged_payload["topics"] = merged_topics

    merged_language = _prefer_non_empty_string(
        preferred.payload.get("language"),
        secondary.payload.get("language"),
    )
    if merged_language:
        merged_payload["language"] = merged_language

    merged_stars = _prefer_larger_int(
        preferred.payload.get("stars"),
        secondary.payload.get("stars"),
    )
    if merged_stars is not None:
        merged_payload["stars"] = merged_stars

    merged_repo = _prefer_non_empty_string(
        preferred.payload.get("repo"),
        secondary.payload.get("repo"),
    )
    if merged_repo:
        merged_payload["repo"] = merged_repo

    merged_author = _prefer_non_empty_string(
        preferred.payload.get("author"),
        secondary.payload.get("author"),
    )
    if merged_author:
        merged_payload["author"] = merged_author

    existing_query = str(existing.payload.get("query") or "")
    incoming_query = str(incoming.payload.get("query") or "")
    merged_query = incoming_query if len(incoming_query) > len(existing_query) else existing_query
    if merged_query:
        merged_payload["query"] = merged_query

    merged_raw_text = _prefer_richer_raw_text(preferred.raw_text, secondary.raw_text)
    merged_title = _prefer_non_empty_string(preferred.title, secondary.title) or preferred.title
    merged_url = _prefer_non_empty_string(preferred.url, secondary.url) or preferred.url

    return Signal(
        source=preferred.source,
        kind=preferred.kind,
        item_id=preferred.item_id,
        title=merged_title,
        url=merged_url,
        published_at=preferred.published_at or secondary.published_at,
        raw_text=merged_raw_text,
        payload=merged_payload,
    )


def _merge_topics(
    first_value: object,
    second_value: object,
) -> list[str]:
    ordered: list[str] = []
    for raw_value in (first_value, second_value):
        if not isinstance(raw_value, list):
            continue
        for topic in raw_value:
            topic_text = str(topic).strip()
            if topic_text and topic_text not in ordered:
                ordered.append(topic_text)
    return ordered


def _prefer_non_empty_string(first_value: object, second_value: object) -> str:
    for raw_value in (first_value, second_value):
        text = str(raw_value or "").strip()
        if text:
            return text
    return ""


def _prefer_larger_int(first_value: object, second_value: object) -> int | None:
    values: list[int] = []
    for raw_value in (first_value, second_value):
        try:
            values.append(int(raw_value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return max(values)


def _prefer_richer_raw_text(first_value: str, second_value: str) -> str:
    if "Matched code path:" in first_value and "Matched code path:" not in second_value:
        return first_value
    if "Matched code path:" in second_value and "Matched code path:" not in first_value:
        return second_value
    if len(second_value) > len(first_value):
        return second_value
    return first_value

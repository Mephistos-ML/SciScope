"""Internal state retained for one incrementally executed Explore search plan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from app.models.ai import AiSearchPlan
from app.models.signal import Signal
from app.services.search.retrieval import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievedCandidates,
    RetrievalMatchEvidence,
)


@dataclass(frozen=True)
class ExploreQueryAttempt:
    """One provider retrieval attempt for one planned query."""

    query: str
    attempt: int
    status: Literal["completed", "timed_out"]
    duration_ms: int
    candidate_count: int


@dataclass(frozen=True)
class ExploreSearchExecution:
    """A completed portion of one AI-generated Explore search plan."""

    ai_search_plan: AiSearchPlan
    executed_queries: tuple[str, ...]
    retrieved: RetrievedCandidates
    attempts: tuple[ExploreQueryAttempt, ...] = ()

    @property
    def pending_queries(self) -> tuple[str, ...]:
        return self.ai_search_plan.queries[len(self.executed_queries) :]


def serialize_execution(execution: ExploreSearchExecution) -> dict[str, object]:
    """Convert resumable execution state into a JSON-safe durable form."""

    return {
        "plan": {
            "status": execution.ai_search_plan.status,
            "queries": list(execution.ai_search_plan.queries),
        },
        "executedQueries": list(execution.executed_queries),
        "retrieved": {
            "candidates": [
                {
                    "repositoryId": candidate.repository_id,
                    "signal": {
                        "source": candidate.signal.source,
                        "kind": candidate.signal.kind,
                        "itemId": candidate.signal.item_id,
                        "title": candidate.signal.title,
                        "url": candidate.signal.url,
                        "publishedAt": (
                            candidate.signal.published_at.isoformat()
                            if candidate.signal.published_at is not None
                            else None
                        ),
                        "rawText": candidate.signal.raw_text,
                        "normalizedText": candidate.signal.normalized_text,
                        "payload": candidate.signal.payload,
                    },
                    "provenance": {
                        "matchedQueries": list(candidate.provenance.matched_queries),
                        "matchedChannels": list(candidate.provenance.matched_channels),
                        "bestRankByChannel": dict(candidate.provenance.best_rank_by_channel),
                        "hitCount": candidate.provenance.hit_count,
                        "matchEvidence": [
                            {
                                "query": evidence.query,
                                "location": evidence.location,
                                "path": evidence.path,
                                "alignment": evidence.alignment,
                                "channel": evidence.channel,
                                "origin": evidence.origin,
                                "retrieval_rank": evidence.retrieval_rank,
                            }
                            for evidence in candidate.provenance.match_evidence
                        ],
                        "origins": list(candidate.provenance.origins),
                    },
                }
                for candidate in execution.retrieved.candidates
            ],
            "sourceStatuses": list(execution.retrieved.source_statuses),
            "successfulSourceCount": execution.retrieved.successful_source_count,
            "partial": execution.retrieved.partial,
            "warnings": list(execution.retrieved.warnings),
        },
        "attempts": [attempt.__dict__ for attempt in execution.attempts],
    }


def deserialize_execution(state: dict[str, Any]) -> ExploreSearchExecution:
    """Restore an execution snapshot persisted by :func:`serialize_execution`."""

    plan = state["plan"]
    retrieved = state["retrieved"]
    candidates = tuple(
        _deserialize_candidate(candidate) for candidate in retrieved["candidates"]
    )
    return ExploreSearchExecution(
        ai_search_plan=AiSearchPlan(
            status=plan["status"],
            queries=tuple(plan["queries"]),
        ),
        executed_queries=tuple(state["executedQueries"]),
        retrieved=RetrievedCandidates(
            candidates=candidates,
            source_statuses=tuple(retrieved["sourceStatuses"]),
            successful_source_count=retrieved["successfulSourceCount"],
            partial=retrieved["partial"],
            warnings=tuple(retrieved["warnings"]),
        ),
        attempts=tuple(ExploreQueryAttempt(**attempt) for attempt in state["attempts"]),
    )


def _deserialize_candidate(value: dict[str, Any]) -> RepositoryCandidate:
    signal = value["signal"]
    published_at = signal["publishedAt"]
    provenance = value["provenance"]
    return RepositoryCandidate(
        repository_id=value["repositoryId"],
        signal=Signal(
            source=signal["source"],
            kind=signal["kind"],
            item_id=signal["itemId"],
            title=signal["title"],
            url=signal["url"],
            published_at=(datetime.fromisoformat(published_at) if published_at else None),
            raw_text=signal["rawText"],
            normalized_text=signal["normalizedText"],
            payload=signal["payload"],
        ),
        provenance=CandidateProvenance(
            matched_queries=tuple(provenance["matchedQueries"]),
            matched_channels=tuple(provenance["matchedChannels"]),
            best_rank_by_channel=provenance["bestRankByChannel"],
            hit_count=provenance["hitCount"],
            match_evidence=tuple(
                RetrievalMatchEvidence(**evidence)
                for evidence in provenance["matchEvidence"]
            ),
            origins=tuple(provenance["origins"]),
        ),
    )

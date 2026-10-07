"""Internal state retained for one incrementally executed Explore search plan."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import math
from typing import Any, Literal, NoReturn, get_args

from app.models.ai import AiSearchPlan, AiSearchPlanStatus
from app.models.signal import Signal
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievedCandidates,
    RetrievalLaneOutcome,
    RetrievalMatchEvidence,
    RetrievalMatchLocation,
    RetrievalMatchOrigin,
)


EXECUTION_SCHEMA_VERSION = 1
ExploreQueryAttemptStatus = Literal["completed", "timed_out"]
ExecutionStateErrorCode = Literal[
    "execution_state_missing", "execution_state_invalid", "execution_state_unsupported",
]


class ExploreExecutionStateError(ValueError):
    """A durable replay state cannot be used safely; messages contain no payload."""

    def __init__(self, code: ExecutionStateErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExploreQueryAttempt:
    """One provider retrieval attempt for one planned query."""

    query: str
    attempt: int
    status: ExploreQueryAttemptStatus
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

    state = {
        "schemaVersion": EXECUTION_SCHEMA_VERSION,
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
            "laneOutcomes": [asdict(outcome) for outcome in execution.retrieved.lane_outcomes],
        },
        "attempts": [asdict(attempt) for attempt in execution.attempts],
    }
    # Domain dataclasses do not enforce the persisted contract themselves.
    # Validate writes with the same contract used to resume work.
    deserialize_execution(state)
    return state


def deserialize_execution(state: object) -> ExploreSearchExecution:
    """Validate and decode only the current durable execution contract."""
    if state is None:
        raise ExploreExecutionStateError("execution_state_missing", "Search execution state is unavailable.")
    if not isinstance(state, dict) or "schemaVersion" not in state:
        _invalid("schemaVersion")
    version = state["schemaVersion"]
    if type(version) is not int:
        _invalid("schemaVersion")
    if version != EXECUTION_SCHEMA_VERSION:
        raise ExploreExecutionStateError(
            "execution_state_unsupported", "Search execution state version is unsupported.",
        )
    root = _object(state, "state", {"schemaVersion", "plan", "executedQueries", "retrieved", "attempts"})
    plan = _object(root["plan"], "plan", {"status", "queries"})
    plan_status = _choice(plan["status"], "plan.status", get_args(AiSearchPlanStatus))
    queries = _texts(plan["queries"], "plan.queries")
    executed = _texts(root["executedQueries"], "executedQueries")
    if len(executed) > len(queries) or executed != queries[:len(executed)]:
        _invalid("executedQueries")
    retrieved = _object(root["retrieved"], "retrieved", {
        "candidates", "sourceStatuses", "successfulSourceCount", "partial", "warnings", "laneOutcomes",
    })
    candidates = tuple(
        _deserialize_candidate(value)
        for value in _list(retrieved["candidates"], "candidates")
    )
    if len({candidate.repository_id for candidate in candidates}) != len(candidates):
        _invalid("candidates.repositoryId")
    partial = retrieved["partial"]
    if type(partial) is not bool:
        _invalid("retrieved.partial")
    attempts = tuple(
        _deserialize_attempt(value) for value in _list(root["attempts"], "attempts")
    )
    if any(attempt.query not in queries for attempt in attempts):
        _invalid("attempts.query")
    return ExploreSearchExecution(
        ai_search_plan=AiSearchPlan(status=plan_status, queries=queries),
        executed_queries=executed,
        retrieved=RetrievedCandidates(
            candidates=candidates,
            source_statuses=tuple(
                _json_object(value, "sourceStatuses")
                for value in _list(retrieved["sourceStatuses"], "sourceStatuses")
            ),
            successful_source_count=_count(retrieved["successfulSourceCount"], "successfulSourceCount"),
            partial=partial,
            warnings=_texts(retrieved["warnings"], "warnings"),
            lane_outcomes=tuple(
                _deserialize_lane(value)
                for value in _list(retrieved["laneOutcomes"], "laneOutcomes")
            ),
        ),
        attempts=attempts,
    )


def _deserialize_candidate(value: object) -> RepositoryCandidate:
    value = _object(value, "candidate", {"repositoryId", "signal", "provenance"})
    signal = _object(value["signal"], "signal", {
        "source", "kind", "itemId", "title", "url", "publishedAt", "rawText", "normalizedText", "payload",
    })
    repository_id = _text(value["repositoryId"], "repositoryId", nonempty=True)
    item_id = _text(signal["itemId"], "signal.itemId", nonempty=True)
    if repository_id != item_id:
        _invalid("signal.itemId")
    published_at = signal["publishedAt"]
    if published_at is not None:
        published_at = _text(published_at, "signal.publishedAt", nonempty=True)
        try:
            published_at = datetime.fromisoformat(published_at)
        except ValueError:
            raise ExploreExecutionStateError(
                "execution_state_invalid", "Search execution state is invalid: signal.publishedAt.",
            ) from None
        if published_at.utcoffset() is None:
            _invalid("signal.publishedAt")
    provenance = _object(value["provenance"], "provenance", {
        "matchedQueries", "matchedChannels", "bestRankByChannel", "hitCount", "matchEvidence", "origins",
    })
    ranks = _object(provenance["bestRankByChannel"], "bestRankByChannel")
    return RepositoryCandidate(
        repository_id=repository_id,
        signal=Signal(
            source=_text(signal["source"], "signal.source", nonempty=True),
            kind=_choice(signal["kind"], "signal.kind", ("repository",)),
            item_id=item_id,
            title=_text(signal["title"], "signal.title"),
            url=_text(signal["url"], "signal.url", nonempty=True),
            published_at=published_at,
            raw_text=_text(signal["rawText"], "signal.rawText"),
            normalized_text=_text(signal["normalizedText"], "signal.normalizedText"),
            payload=_json_object(signal["payload"], "signal.payload"),
        ),
        provenance=CandidateProvenance(
            matched_queries=_texts(provenance["matchedQueries"], "matchedQueries"),
            matched_channels=_texts(provenance["matchedChannels"], "matchedChannels"),
            best_rank_by_channel={
                _text(key, "bestRankByChannel", nonempty=True):
                _count(rank, "bestRankByChannel", minimum=1)
                for key, rank in ranks.items()
            },
            hit_count=_count(provenance["hitCount"], "hitCount"),
            match_evidence=tuple(
                _deserialize_evidence(item)
                for item in _list(provenance["matchEvidence"], "matchEvidence")
            ),
            origins=tuple(
                _choice(origin, "origins", get_args(RetrievalMatchOrigin))
                for origin in _texts(provenance["origins"], "origins")
            ),
        ),
    )


def _deserialize_evidence(value: object) -> RetrievalMatchEvidence:
    value = _object(value, "matchEvidence", {
        "query", "location", "path", "alignment", "channel", "origin", "retrieval_rank",
    })
    alignment = value["alignment"]
    if type(alignment) not in (int, float) or not 0 <= alignment <= 1 or not math.isfinite(alignment):
        _invalid("matchEvidence.alignment")
    rank = value["retrieval_rank"]
    return RetrievalMatchEvidence(
        query=_text(value["query"], "matchEvidence.query", nonempty=True),
        location=_choice(value["location"], "matchEvidence.location", get_args(RetrievalMatchLocation)),
        path=_text(value["path"], "matchEvidence.path"),
        alignment=alignment,
        channel=_text(value["channel"], "matchEvidence.channel", nonempty=True),
        origin=_choice(value["origin"], "matchEvidence.origin", get_args(RetrievalMatchOrigin)),
        retrieval_rank=None if rank is None else _count(rank, "matchEvidence.retrieval_rank", minimum=1),
    )


def _deserialize_attempt(value: object) -> ExploreQueryAttempt:
    value = _object(value, "attempt", {"query", "attempt", "status", "duration_ms", "candidate_count"})
    return ExploreQueryAttempt(
        query=_text(value["query"], "attempt.query", nonempty=True),
        attempt=_count(value["attempt"], "attempt.attempt", minimum=1),
        status=_choice(value["status"], "attempt.status", get_args(ExploreQueryAttemptStatus)),
        duration_ms=_count(value["duration_ms"], "attempt.duration_ms"),
        candidate_count=_count(value["candidate_count"], "attempt.candidate_count"),
    )


def _deserialize_lane(value: object) -> RetrievalLaneOutcome:
    value = _object(value, "laneOutcome", {
        "source", "channel", "status", "candidate_count", "duration_ms", "query", "attempt",
        "retry_after_seconds", "error_code", "error_message",
    })
    retry = value["retry_after_seconds"]
    return RetrievalLaneOutcome(
        source=_text(value["source"], "laneOutcome.source", nonempty=True),
        channel=_text(value["channel"], "laneOutcome.channel", nonempty=True),
        status=_text(value["status"], "laneOutcome.status", nonempty=True),
        candidate_count=_count(value["candidate_count"], "laneOutcome.candidate_count"),
        duration_ms=_count(value["duration_ms"], "laneOutcome.duration_ms"),
        query=_text(value["query"], "laneOutcome.query"),
        attempt=_count(value["attempt"], "laneOutcome.attempt", minimum=1),
        retry_after_seconds=None if retry is None else _count(retry, "laneOutcome.retry_after_seconds"),
        error_code=_optional_text(value["error_code"], "laneOutcome.error_code"),
        error_message=_optional_text(value["error_message"], "laneOutcome.error_message"),
    )


def _invalid(field: str) -> NoReturn:
    raise ExploreExecutionStateError("execution_state_invalid", f"Search execution state is invalid: {field}.")


def _object(value: object, field: str, keys: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _invalid(field)
    if keys is not None and value.keys() != keys:
        _invalid(field)
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _invalid(field)
    return value


def _text(value: object, field: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        _invalid(field)
    return value


def _optional_text(value: object, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _texts(value: object, field: str) -> tuple[str, ...]:
    return tuple(_text(item, field, nonempty=True) for item in _list(value, field))


def _count(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _invalid(field)
    return value


def _choice(value: object, field: str, choices: tuple[str, ...]) -> Any:
    if not isinstance(value, str) or value not in choices:
        _invalid(field)
    return value


def _json_object(value: object, field: str) -> dict[str, Any]:
    result = _object(value, field)
    _validate_json(result, field)
    return result


def _validate_json(value: object, field: str) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, dict):
        for item in _object(value, field).values():
            _validate_json(item, field)
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item, field)
        return
    _invalid(field)

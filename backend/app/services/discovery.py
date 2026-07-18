"""Discovery orchestration for building topic-specific watched entity memory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models.entity import Entity, TopicEntityMatch
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile
from app.services.matching import match_signal_to_profile
from app.services.normalization import normalize_raw_signal
from app.sources.github.discovery import discover_repository_candidates
from app.sources.github.query_builder import build_repository_search_queries
from app.storage.entities import upsert_entities, upsert_topic_entity_matches
from app.storage.seen_signals import DB_PATH


@dataclass(frozen=True)
class DiscoveryResult:
    """Summary of one discovery run."""

    topic_slug: str
    queries: tuple[str, ...]
    candidate_count: int
    entity_count: int
    matched_entity_count: int

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-friendly representation for debug visibility."""

        return {
            "topicSlug": self.topic_slug,
            "queries": list(self.queries),
            "candidateCount": self.candidate_count,
            "entityCount": self.entity_count,
            "matchedEntityCount": self.matched_entity_count,
        }


def discover_github_entities_for_profile(
    profile: ResearchProfile,
    *,
    db_path: Path = DB_PATH,
) -> DiscoveryResult:
    """Discover GitHub repositories relevant to one research profile."""

    queries = build_repository_search_queries(profile)
    candidates = discover_repository_candidates(queries)

    deduped_candidates = _dedupe_repository_candidates(candidates)
    entities: list[Entity] = []
    matches: list[TopicEntityMatch] = []

    for raw_signal in deduped_candidates.values():
        normalized_signal = normalize_raw_signal(raw_signal)
        match = match_signal_to_profile(normalized_signal, profile)

        if not match.matched:
            continue

        repo_name = str(raw_signal.payload.get("repo") or raw_signal.title)
        entities.append(
            Entity(
                entity_id=raw_signal.item_id,
                source=raw_signal.source,
                entity_type="repository",
                canonical_name=repo_name,
                url=raw_signal.url,
                metadata={
                    "query": raw_signal.payload.get("query"),
                    "topics": raw_signal.payload.get("topics", []),
                    "language": raw_signal.payload.get("language"),
                    "stars": raw_signal.payload.get("stars"),
                },
            )
        )
        matches.append(
            TopicEntityMatch(
                topic_slug=profile.topic_slug,
                entity_id=raw_signal.item_id,
                source=raw_signal.source,
                matched_terms=match.matched_terms,
                excluded_terms=match.excluded_terms,
                score=match.score,
                active=True,
                reason=match.reason,
                metadata={
                    "repo": repo_name,
                    "query": raw_signal.payload.get("query"),
                },
            )
        )

    upsert_entities(entities, db_path=db_path)
    upsert_topic_entity_matches(matches, db_path=db_path)

    return DiscoveryResult(
        topic_slug=profile.topic_slug,
        queries=queries,
        candidate_count=len(candidates),
        entity_count=len(entities),
        matched_entity_count=len(matches),
    )


def _dedupe_repository_candidates(
    candidates: list[RawSignal],
) -> dict[str, RawSignal]:
    deduped: dict[str, RawSignal] = {}
    for signal in candidates:
        existing = deduped.get(signal.item_id)
        if existing is None:
            deduped[signal.item_id] = signal
            continue

        existing_query = str(existing.payload.get("query") or "")
        incoming_query = str(signal.payload.get("query") or "")
        if len(incoming_query) > len(existing_query):
            deduped[signal.item_id] = signal

    return deduped

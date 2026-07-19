"""Source-agnostic discovery result models."""

from __future__ import annotations

from dataclasses import dataclass


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

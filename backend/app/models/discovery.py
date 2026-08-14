"""Source-agnostic discovery result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryResult:
    """Summary of one discovery run."""

    subscription_id: str
    queries: tuple[str, ...]
    candidate_count: int
    repository_count: int
    matched_repository_count: int

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-friendly representation for debug visibility."""

        return {
            "subscriptionId": self.subscription_id,
            "queries": list(self.queries),
            "candidateCount": self.candidate_count,
            "repositoryCount": self.repository_count,
            "matchedRepositoryCount": self.matched_repository_count,
        }

"""Explicit capabilities needed to execute an Explore search."""

from dataclasses import dataclass

from app.services.ai.embeddings import EmbeddingProvider
from app.services.ai.planner import AiSearchPlanner
from app.services.search.retrieval.models import RetrievalLane


@dataclass(frozen=True)
class ExploreDependencies:
    planner: AiSearchPlanner
    lanes: tuple[RetrievalLane, ...]
    embeddings: EmbeddingProvider | None

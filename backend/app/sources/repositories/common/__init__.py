"""Shared helpers for repository-style source adapters."""

from app.sources.repositories.common.factories import (
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    build_repository_candidate_signal,
    build_repository_entity,
    build_repository_release_checkpoint,
    build_repository_release_signal,
    build_repository_text,
    build_repository_topic_match,
    read_repository_name,
)
from app.sources.repositories.common.models import RepositoryCandidate, RepositoryRelease
from app.sources.repositories.common.query_builder import (
    MAX_DISCOVERY_QUERIES,
    build_repository_search_queries,
)

__all__ = [
    "MAX_DISCOVERY_QUERIES",
    "REPOSITORY_RELEASE_CHECKPOINT_KEY",
    "RepositoryCandidate",
    "RepositoryRelease",
    "build_repository_candidate_signal",
    "build_repository_entity",
    "build_repository_release_checkpoint",
    "build_repository_release_signal",
    "build_repository_search_queries",
    "build_repository_text",
    "build_repository_topic_match",
    "read_repository_name",
]

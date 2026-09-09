"""Persistence helpers for repositories."""

from app.storage.repositories.repositories import (
    get_repository,
    find_catalog_repository_matches,
    list_repositories,
    list_repositories_by_ids,
    list_repository_search_evidence,
    upsert_repositories,
    upsert_repository_search_evidence,
)
from app.storage.repositories.semantic import (
    filter_missing_profile_embeddings,
    filter_missing_query_embeddings,
    find_semantic_profiles,
    find_semantic_query_evidence,
    semantic_catalog_is_available,
    upsert_profile_embeddings,
    upsert_query_embeddings,
)

__all__ = [
    "find_catalog_repository_matches",
    "find_semantic_profiles",
    "find_semantic_query_evidence",
    "filter_missing_profile_embeddings",
    "filter_missing_query_embeddings",
    "get_repository",
    "list_repositories",
    "list_repositories_by_ids",
    "list_repository_search_evidence",
    "semantic_catalog_is_available",
    "upsert_repositories",
    "upsert_repository_search_evidence",
    "upsert_profile_embeddings",
    "upsert_query_embeddings",
]

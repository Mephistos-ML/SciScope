"""GitHub source namespace."""

from app.sources.github.discovery import discover_repository_candidates
from app.sources.github.monitor import load_repo_activity
from app.sources.github.query_builder import build_repository_search_queries

__all__ = [
    "build_repository_search_queries",
    "discover_repository_candidates",
    "load_repo_activity",
]

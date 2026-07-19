"""Compatibility shim for shared repository-family query building."""

from __future__ import annotations

from app.sources.repositories.common.query_builder import (
    MAX_DISCOVERY_QUERIES,
    build_repository_search_queries,
)


__all__ = ["MAX_DISCOVERY_QUERIES", "build_repository_search_queries"]

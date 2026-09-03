"""Populate pgvector embeddings for the current repository catalog."""

from __future__ import annotations

from app.config import DATABASE_URL
from app.services.search.semantic import backfill_semantic_catalog


if __name__ == "__main__":
    repository_count, query_count = backfill_semantic_catalog(database_url=DATABASE_URL)
    print(
        "Semantic catalog backfill completed: "
        f"{repository_count} repository profiles, {query_count} unique queries."
    )

"""Repository domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Repository:
    """One provider repository in SciScope's global catalog."""

    repository_id: str
    source: str
    full_name: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)
    provider_repository_id: str = ""
    owner_login: str = ""
    description: str = ""
    language: str = ""
    stars: int = 0
    topics: tuple[str, ...] = ()
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_retrieved_at: datetime | None = None
    provider_updated_at: datetime | None = None


@dataclass(frozen=True)
class RepositorySearchEvidence:
    """A durable, query-specific reason that a repository was retrieved."""

    repository_id: str
    query_normalized: str
    channel: str
    match_location: str
    matched_path: str = ""
    matched_excerpt: str = ""
    provider_rank: int | None = None
    hit_count: int = 1
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(frozen=True)
class CatalogRepositoryMatch:
    """A repository profile plus the local evidence that matched a query plan."""

    repository: Repository
    matched_queries: tuple[str, ...]
    evidence: tuple[RepositorySearchEvidence, ...]


@dataclass(frozen=True)
class RepositoryCheckpoint:
    """Monitoring checkpoint for one watched repository."""

    subscription_id: str
    repository_id: str
    source: str
    checkpoint_key: str
    checkpoint_value: str
    updated_at: datetime

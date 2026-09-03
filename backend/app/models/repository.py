"""Repository domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


_REPOSITORY_ID_MARKER = ":repo:"


def build_repository_id(source: str, provider_repository_id: str) -> str:
    """Build SciScope's canonical identity for one provider repository."""

    normalized_source = source.strip().casefold()
    normalized_provider_id = provider_repository_id.strip()
    if not normalized_source or not normalized_provider_id:
        raise ValueError("Repository source and provider repository ID are required.")
    if "/" in normalized_provider_id:
        raise ValueError("Repository identity must use the provider-native ID, not full_name.")
    return f"{normalized_source}{_REPOSITORY_ID_MARKER}{normalized_provider_id}"


def parse_repository_id(repository_id: str, *, source: str) -> str:
    """Read and validate the provider-native portion of a canonical repository ID."""

    normalized_source = source.strip().casefold()
    expected_prefix = f"{normalized_source}{_REPOSITORY_ID_MARKER}"
    normalized_repository_id = repository_id.strip()
    if not normalized_source or not normalized_repository_id.startswith(expected_prefix):
        raise ValueError("Repository ID does not match its provider source.")

    provider_repository_id = normalized_repository_id.removeprefix(expected_prefix)
    if not provider_repository_id or "/" in provider_repository_id:
        raise ValueError("Repository ID must contain a provider-native ID.")
    return provider_repository_id


def parse_provider_updated_at(value: object) -> datetime | None:
    """Normalize an optional provider ISO-8601 activity timestamp."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


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

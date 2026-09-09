"""Shared models for repository-style source adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.models.repository import Repository
from app.models.signal import Signal


@dataclass(frozen=True)
class JsonResponse:
    """JSON payload returned by a provider request and its final URL."""

    payload: object
    url: str


@dataclass(frozen=True)
class RepositoryActivity:
    """Repository events returned by one provider scan."""

    signals: tuple[Signal, ...]
    redirected: bool = False


class RepositoryMonitor(Protocol):
    """Source adapter contract for repository monitoring."""

    def load_repository_activity(
        self,
        repository: Repository,
        *,
        release_started_after: datetime | None,
        commit_started_after: datetime | None,
    ) -> RepositoryActivity: ...

    def refresh_repository_profile(self, repository: Repository) -> Repository: ...


@dataclass(frozen=True)
class RepositoryCandidate:
    """One discovered repository candidate before topic admission."""

    source: str
    full_name: str
    url: str
    query: str
    provider_repository_id: str = ""
    description: str = ""
    owner_login: str = ""
    language: str = ""
    stars: int = 0
    topics: tuple[str, ...] = ()
    matched_path: str = ""
    matched_excerpt: str = ""
    provider_updated_at: datetime | None = None


@dataclass(frozen=True)
class RepositoryRelease:
    """One release-like event emitted by a repository source."""

    source: str
    repo_full_name: str
    release_id: str
    title: str
    url: str
    published_at: datetime
    tag_name: str = ""
    body: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RepositoryCommit:
    """One default-branch commit event emitted by a repository source."""

    source: str
    repo_full_name: str
    commit_sha: str
    title: str
    url: str
    published_at: datetime
    branch: str = ""
    author_name: str = ""
    body: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

"""Shared models for repository-style source adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RepositoryCandidate:
    """One discovered repository candidate before topic admission."""

    source: str
    full_name: str
    url: str
    query: str
    description: str = ""
    owner_login: str = ""
    language: str = ""
    stars: int = 0
    topics: tuple[str, ...] = ()


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

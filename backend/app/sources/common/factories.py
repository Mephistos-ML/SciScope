"""Shared repository-family builders and metadata helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.models.repository import (
    Repository,
    RepositoryCheckpoint,
)
from app.models.signal import RawSignal
from app.sources.common.models import RepositoryCandidate, RepositoryRelease


REPOSITORY_RELEASE_CHECKPOINT_KEY = "latest_release_published_at"


def build_repository_candidate_signal(candidate: RepositoryCandidate) -> RawSignal:
    """Convert one repository candidate into the shared raw-signal shape."""

    return RawSignal(
        source=candidate.source,
        kind="repository",
        item_id=f"{candidate.source}:repo:{candidate.full_name}",
        title=candidate.full_name,
        url=candidate.url,
        published_at=None,
        raw_text=build_repository_text(
            full_name=candidate.full_name,
            description=candidate.description,
            topics=candidate.topics,
            language=candidate.language,
        ),
        payload={
            "repo": candidate.full_name,
            "author": candidate.owner_login,
            "topics": list(candidate.topics),
            "language": candidate.language,
            "stars": candidate.stars,
            "query": candidate.query,
        },
    )


def build_repository_entity(raw_signal: RawSignal) -> Repository:
    """Build a watched repository from an admitted raw signal."""

    repo_name = str(raw_signal.payload.get("repo") or raw_signal.title)
    return Repository(
        repository_id=raw_signal.item_id,
        source=raw_signal.source,
        full_name=repo_name,
        url=raw_signal.url,
        metadata={
            "repo": repo_name,
            "query": raw_signal.payload.get("query"),
            "topics": raw_signal.payload.get("topics", []),
            "language": raw_signal.payload.get("language"),
            "stars": raw_signal.payload.get("stars"),
        },
    )


def build_repository_release_signal(release: RepositoryRelease) -> RawSignal:
    """Convert one repository release event into the shared raw-signal shape."""

    return RawSignal(
        source=release.source,
        kind="release",
        item_id=f"{release.repo_full_name}:release:{release.release_id}",
        title=f"{release.repo_full_name} release {release.title}",
        url=release.url,
        published_at=release.published_at,
        raw_text=f"{release.title}\n\n{release.body}\n\n{release.tag_name}".strip(),
        payload={
            "repo": release.repo_full_name,
            "tag_name": release.tag_name,
            **release.metadata,
        },
    )


def build_repository_release_checkpoint(
    subscription_id: str,
    repository: Repository,
    *,
    latest_published_at: datetime | None,
    fallback_started_after: datetime,
) -> RepositoryCheckpoint | None:
    """Build the next release cursor for one watched repository."""

    checkpoint_value = latest_published_at or fallback_started_after
    if checkpoint_value is None:
        return None

    return RepositoryCheckpoint(
        subscription_id=subscription_id,
        repository_id=repository.repository_id,
        source=repository.source,
        checkpoint_key=REPOSITORY_RELEASE_CHECKPOINT_KEY,
        checkpoint_value=checkpoint_value.astimezone(UTC).isoformat(),
        updated_at=datetime.now(UTC),
    )


def read_repository_name(repository: Repository) -> str | None:
    """Read a normalized repository full name from one repository."""

    repo_name = repository.metadata.get("repo")
    if not isinstance(repo_name, str) or not repo_name.strip():
        repo_name = repository.full_name
    repo_name = repo_name.strip()
    if repo_name:
        return repo_name
    return None


def build_repository_text(
    *,
    full_name: str,
    description: str,
    topics: Sequence[str],
    language: str,
) -> str:
    """Build one normalized repository text blob for matching."""

    parts: list[str] = [full_name, description]
    if topics:
        parts.append(" ".join(topic.strip() for topic in topics if topic.strip()))
    if language.strip():
        parts.append(language.strip())
    return "\n".join(part.strip() for part in parts if part.strip())

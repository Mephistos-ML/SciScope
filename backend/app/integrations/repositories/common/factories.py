"""Shared repository-family builders and metadata helpers."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.repository import (
    Repository,
    build_repository_id,
    parse_provider_updated_at,
)
from app.models.signal import Signal
from app.integrations.repositories.common.models import (
    RepositoryCandidate,
    RepositoryCommit,
    RepositoryRelease,
)


MAX_PROVIDER_EVENT_TEXT_BYTES = 32 * 1024
MAX_PROVIDER_EVENT_TITLE_BYTES = 512


def build_repository_candidate_signal(candidate: RepositoryCandidate) -> Signal:
    """Convert one repository candidate into the shared signal shape."""

    return Signal(
        source=candidate.source,
        kind="repository",
        item_id=build_repository_id(
            candidate.source,
            candidate.provider_repository_id,
        ),
        title=candidate.full_name,
        url=candidate.url,
        published_at=None,
        raw_text=build_repository_text(
            full_name=candidate.full_name,
            description=candidate.description,
            topics=candidate.topics,
            language=candidate.language,
            matched_path=candidate.matched_path,
            matched_excerpt=candidate.matched_excerpt,
        ),
        payload={
            "repo": candidate.full_name,
            "provider_repository_id": candidate.provider_repository_id,
            "author": candidate.owner_login,
            "description": candidate.description,
            "topics": list(candidate.topics),
            "language": candidate.language,
            "stars": candidate.stars,
            "query": candidate.query,
            "matched_path": candidate.matched_path,
            "matched_excerpt": candidate.matched_excerpt,
            "provider_updated_at": (
                candidate.provider_updated_at.isoformat()
                if candidate.provider_updated_at is not None
                else None
            ),
        },
    )


def build_repository_entity(signal: Signal) -> Repository:
    """Build a watched repository from one admitted signal."""

    repo_name = str(signal.payload.get("repo") or signal.title)
    return Repository(
        repository_id=signal.item_id,
        source=signal.source,
        full_name=repo_name,
        url=signal.url,
        metadata={
            "repo": repo_name,
        },
        provider_repository_id=str(signal.payload.get("provider_repository_id") or ""),
        owner_login=str(signal.payload.get("author") or ""),
        description=str(signal.payload.get("description") or ""),
        language=str(signal.payload.get("language") or ""),
        stars=int(signal.payload.get("stars") or 0),
        topics=tuple(
            str(topic)
            for topic in signal.payload.get("topics", [])
            if str(topic).strip()
        ),
        provider_updated_at=parse_provider_updated_at(
            signal.payload.get("provider_updated_at")
        ),
    )


def build_repository_release_signal(release: RepositoryRelease) -> Signal:
    """Convert one repository release event into the shared signal shape."""

    original_title = release.title.strip() or release.tag_name or "Release"
    title = _truncate_provider_text(original_title, max_bytes=MAX_PROVIDER_EVENT_TITLE_BYTES)
    content = f"{title}\n\n{release.body.strip()}".strip()
    raw_text = _truncate_provider_text(content, max_bytes=MAX_PROVIDER_EVENT_TEXT_BYTES)
    return Signal(
        source=release.source,
        kind="release",
        item_id=f"{release.repo_full_name}:release:{release.release_id}",
        title=title,
        url=release.url,
        published_at=release.published_at,
        raw_text=raw_text,
        payload={
            "repo": release.repo_full_name,
            "tag_name": release.tag_name,
            **release.metadata,
            **({"text_truncated": True} if title != original_title or raw_text != content else {}),
        },
    )


def build_repository_commit_signal(commit: RepositoryCommit) -> Signal:
    """Convert one repository commit fact into the shared signal shape."""

    original_title = commit.title.strip().splitlines()[0] if commit.title.strip() else commit.commit_sha[:7]
    title = _truncate_provider_text(original_title, max_bytes=MAX_PROVIDER_EVENT_TITLE_BYTES)
    body = commit.body.strip()
    if body and body.splitlines()[0].strip() == original_title:
        body = body.partition("\n")[2].strip()
    content = f"{title}\n\n{body}".strip()
    raw_text = _truncate_provider_text(content, max_bytes=MAX_PROVIDER_EVENT_TEXT_BYTES)
    return Signal(
        source=commit.source,
        kind="commit",
        item_id=f"{commit.repo_full_name}:commit:{commit.commit_sha}",
        title=title,
        url=commit.url,
        published_at=commit.published_at,
        raw_text=raw_text,
        payload={
            "repo": commit.repo_full_name,
            "branch": commit.branch,
            "commit_sha": commit.commit_sha,
            "author_name": commit.author_name,
            **commit.metadata,
            **({"text_truncated": True} if title != original_title or raw_text != content else {}),
        },
    )


def _truncate_provider_text(value: str, *, max_bytes: int) -> str:
    """Bound provider text without splitting a UTF-8 character."""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    suffix = "…"
    truncated = encoded[:max_bytes - len(suffix.encode("utf-8"))]
    return f"{truncated.decode('utf-8', errors='ignore').rstrip()}{suffix}"


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
    matched_path: str,
    matched_excerpt: str,
) -> str:
    """Build one normalized repository text blob for matching."""

    parts: list[str] = [full_name, description]
    if matched_path.strip():
        parts.append(f"Matched code path: {matched_path.strip()}")
    if topics:
        parts.append(" ".join(topic.strip() for topic in topics if topic.strip()))
    if language.strip():
        parts.append(language.strip())
    if matched_excerpt.strip():
        parts.append(matched_excerpt.strip())
    return "\n".join(part.strip() for part in parts if part.strip())

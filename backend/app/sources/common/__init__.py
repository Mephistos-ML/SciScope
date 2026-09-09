"""Shared helpers for repository-style source adapters."""

from app.sources.common.factories import (
    MAX_PROVIDER_EVENT_BODY_BYTES,
    REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    build_repository_candidate_signal,
    build_repository_entity,
    build_repository_main_commit_checkpoint,
    build_repository_main_commit_signal,
    build_repository_release_checkpoint,
    build_repository_release_signal,
    build_repository_text,
    read_repository_name,
)
from app.sources.common.deadlines import (
    raise_source_timeout_error,
    read_remaining_timeout_seconds,
)
from app.sources.common.models import (
    JsonResponse,
    RepositoryActivity,
    RepositoryCandidate,
    RepositoryCommit,
    RepositoryMonitor,
    RepositoryRelease,
)
from app.sources.common.source_status import (
    RepositorySourceError,
    RepositorySourceStatusCode,
    build_source_status,
)

__all__ = [
    "REPOSITORY_RELEASE_CHECKPOINT_KEY",
    "REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY",
    "MAX_PROVIDER_EVENT_BODY_BYTES",
    "JsonResponse",
    "RepositoryActivity",
    "RepositoryCandidate",
    "RepositoryCommit",
    "RepositoryMonitor",
    "RepositoryRelease",
    "RepositorySourceError",
    "RepositorySourceStatusCode",
    "build_repository_candidate_signal",
    "build_repository_entity",
    "build_repository_main_commit_checkpoint",
    "build_repository_main_commit_signal",
    "build_repository_release_checkpoint",
    "build_repository_release_signal",
    "raise_source_timeout_error",
    "read_remaining_timeout_seconds",
    "build_source_status",
    "build_repository_text",
    "read_repository_name",
]

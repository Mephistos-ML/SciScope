"""Shared source status helpers for repository adapters."""

from __future__ import annotations

from typing import Literal

RepositorySourceStatusCode = Literal[
    "ok",
    "disabled",
    "misconfigured",
    "unauthorized",
    "rate_limited",
    "timed_out",
    "error",
]


class RepositorySourceError(RuntimeError):
    """One repository source failed in a classified, user-facing way."""

    def __init__(
        self,
        *,
        source: str,
        status: RepositorySourceStatusCode,
        public_message: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(public_message)
        self.source = source
        self.status = status
        self.public_message = public_message
        self.retry_after_seconds = retry_after_seconds


def build_source_status(
    *,
    source: str,
    status: RepositorySourceStatusCode,
    candidate_count: int = 0,
    error: str | None = None,
) -> dict[str, object]:
    """Build one compact source-status payload for API responses."""

    return {
        "source": source,
        "status": status,
        "candidateCount": candidate_count,
        "error": error,
    }

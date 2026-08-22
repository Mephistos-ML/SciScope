"""Shared deadline helpers for outbound source requests."""

from __future__ import annotations

from time import monotonic

from app.sources.common.source_status import RepositorySourceError

SOURCE_DISPLAY_NAMES = {
    "github": "GitHub",
    "gitlab": "GitLab",
}


def read_remaining_timeout_seconds(
    *,
    deadline_monotonic: float | None,
    fallback_seconds: float,
) -> float:
    """Return one clipped request timeout for the remaining budget."""

    if deadline_monotonic is None:
        return fallback_seconds

    remaining_seconds = deadline_monotonic - monotonic()
    if remaining_seconds <= 0:
        raise TimeoutError("The request budget has expired.")
    return min(fallback_seconds, max(remaining_seconds, 0.1))


def raise_source_timeout_error(*, source: str, operation: str) -> None:
    """Raise one classified timeout error for a source operation."""

    display_name = SOURCE_DISPLAY_NAMES.get(source, source.title())
    raise RepositorySourceError(
        source=source,
        status="timed_out",
        public_message=f"{display_name} {operation} timed out.",
    )

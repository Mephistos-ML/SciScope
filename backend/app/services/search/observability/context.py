"""Search observability context objects."""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4


@dataclass(frozen=True)
class SearchLogContext:
    """Stable log context for one search run."""

    request_id: str
    topic_hash: str
    job_id: str | None = None

    def with_job_id(self, job_id: str) -> SearchLogContext:
        """Return the same context bound to one async job id."""

        return replace(self, job_id=job_id)


def build_request_id() -> str:
    """Return one opaque request identifier."""

    return uuid4().hex

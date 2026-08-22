"""GitCode monitoring placeholder."""

from __future__ import annotations

from datetime import datetime

from app.models.signal import Signal


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[Signal]:
    """Return no signals until the GitCode source is implemented."""

    del repo_full_name, started_after
    return []

"""GitVerse monitoring placeholder."""

from __future__ import annotations

from datetime import datetime

from app.models.repository import Repository
from app.models.signal import RawSignal


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[RawSignal]:
    """Return no signals until the GitVerse source is implemented."""

    del repo_full_name, started_after
    return []


def load_gitverse_signals_for_subscription(
    subscription_id: str,
    repository: Repository,
) -> list[RawSignal]:
    """Return no signals until the GitVerse source is implemented."""

    del subscription_id, repository
    return []

"""Gitee monitoring placeholder."""

from __future__ import annotations

from datetime import datetime

from app.models.signal import RawSignal
from app.models.subscription import SubscriptionQueryProfile


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[RawSignal]:
    """Return no signals until the Gitee source is implemented."""

    del repo_full_name, started_after
    return []


def load_gitee_signals_for_profile(
    profile: SubscriptionQueryProfile,
) -> list[RawSignal]:
    """Return no signals until the Gitee source is implemented."""

    del profile
    return []

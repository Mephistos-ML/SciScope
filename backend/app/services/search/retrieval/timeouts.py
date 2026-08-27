"""Timeout helpers for external retrieval."""

from __future__ import annotations

import logging
from time import monotonic

from app.config import (
    EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS,
    EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS,
)


def build_lane_deadline_monotonic(
    *,
    channel_name: str,
    soft_deadline_monotonic: float | None,
    hard_deadline_monotonic: float | None,
) -> float | None:
    """Build one deadline for a single retrieval lane."""

    lane_budget_seconds = (
        EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS
        if channel_name == "code_search"
        else EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS
    )
    lane_deadline_monotonic = monotonic() + lane_budget_seconds
    deadline_candidates = [lane_deadline_monotonic]
    if soft_deadline_monotonic is not None:
        deadline_candidates.append(soft_deadline_monotonic)
    if hard_deadline_monotonic is not None:
        deadline_candidates.append(hard_deadline_monotonic)
    return min(deadline_candidates)


def is_deadline_reached(deadline_monotonic: float | None) -> bool:
    """Return whether one deadline has been reached."""

    return deadline_monotonic is not None and monotonic() >= deadline_monotonic


def read_wait_timeout_seconds(
    *,
    soft_deadline_monotonic: float | None,
    hard_deadline_monotonic: float | None,
) -> float | None:
    """Return the remaining wait time for the next lane result."""

    deadline_candidates = [
        deadline
        for deadline in (soft_deadline_monotonic, hard_deadline_monotonic)
        if deadline is not None
    ]
    if not deadline_candidates:
        return None

    remaining_seconds = min(deadline_candidates) - monotonic()
    return max(0.0, remaining_seconds)


def build_deadline_warning(
    *,
    soft_deadline_monotonic: float | None,
    hard_deadline_monotonic: float | None,
) -> tuple[str, int]:
    """Return one user-facing deadline warning and its log level."""

    if is_deadline_reached(soft_deadline_monotonic):
        return (
            "Search completed with partial coverage because the time budget expired before all lanes finished.",
            logging.INFO,
        )
    return (
        "Search completed with partial coverage because the hard timeout was reached.",
        logging.WARNING,
    )

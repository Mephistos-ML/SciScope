"""AI-oriented search planning models."""

from __future__ import annotations

from collections.abc import Iterable

from dataclasses import dataclass
from typing import Literal

AiSearchPlanStatus = Literal["pending", "ready"]


@dataclass(frozen=True)
class AiSearchPlan:
    """Repository-search intent ready for downstream discovery."""

    status: AiSearchPlanStatus
    queries: tuple[str, ...]


@dataclass(frozen=True)
class AiPlannerIdentity:
    """Planner provenance recorded for the implementation that executes a plan."""

    mode: str
    model: str | None
    reasoning_effort: str | None


def normalize_search_queries(values: Iterable[str]) -> tuple[str, ...]:
    """Normalize one query list for one AI-generated source plan."""

    normalized_values: list[str] = []
    seen: set[str] = set()

    for raw_value in values:
        normalized = " ".join(str(raw_value).split()).strip()
        if not normalized:
            continue

        folded = normalized.casefold()
        if folded in seen:
            continue

        seen.add(folded)
        normalized_values.append(normalized)

    return tuple(normalized_values)


class AiDependencyError(RuntimeError):
    """An AI dependency is unavailable or returned unusable data."""


class AiConfigurationError(AiDependencyError):
    """Required AI deployment configuration is absent."""


class AiResponseError(AiDependencyError):
    """Generated output does not satisfy the capability contract."""

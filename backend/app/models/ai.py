"""AI-oriented search planning models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SearchScope = Literal["repositories", "all"]
AiSourceType = Literal["repositories"]
AiSearchPlanStatus = Literal["pending", "ready"]


@dataclass(frozen=True)
class AiSourcePlan:
    """One source-scoped query plan derived from user intent."""

    source_type: AiSourceType
    queries: tuple[str, ...]


@dataclass(frozen=True)
class AiSearchPlan:
    """Structured search intent ready for downstream discovery layers."""

    search_scope: SearchScope
    status: AiSearchPlanStatus
    source_plans: tuple[AiSourcePlan, ...]

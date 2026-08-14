"""AI-oriented search planning models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AiSearchPlanStatus = Literal["pending", "ready"]


@dataclass(frozen=True)
class AiSearchPlan:
    """Repository-search intent ready for downstream discovery."""

    status: AiSearchPlanStatus
    queries: tuple[str, ...]

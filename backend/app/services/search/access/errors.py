"""Domain error for denied Explore admission."""

from __future__ import annotations

from app.models.explore_access import ExploreAccessDecision


class ExploreAccessDeniedError(RuntimeError):
    """A denied admission decision, independent of its delivery transport."""

    def __init__(self, decision: ExploreAccessDecision) -> None:
        if decision.allowed:
            raise ValueError("Allowed explore decisions cannot be converted to errors.")
        if decision.message is None or decision.code is None:
            raise ValueError("Denied explore decisions must include code and message.")
        self.decision = decision
        super().__init__(decision.message)

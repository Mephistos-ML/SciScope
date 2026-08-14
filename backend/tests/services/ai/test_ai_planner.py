"""AI planner tests."""

from __future__ import annotations

from app import config
from app.models.ai import AiSearchPlan
from app.services.ai.planner import build_ai_search_plan


def test_build_ai_search_plan_returns_pending_plan_in_bootstrap_mode() -> None:
    plan = build_ai_search_plan(topic_description="Paramagnetic NMR analysis workflows")

    assert plan.status == "pending"
    assert plan.queries == ()


def test_build_ai_search_plan_uses_openai_planner_when_mode_is_openai(
    monkeypatch,
) -> None:
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")

    def _build_search_plan(_self, **kwargs) -> AiSearchPlan:
        assert kwargs["topic_description"] == "Paramagnetic NMR analysis workflows"
        return AiSearchPlan(
            status="ready",
            queries=("paramagnetic nmr software", "pcs tensor fitting"),
        )

    monkeypatch.setattr(
        "app.services.ai.planner.OpenAiSearchPlanner.build_search_plan",
        _build_search_plan,
    )

    plan = build_ai_search_plan(topic_description="Paramagnetic NMR analysis workflows")

    assert plan.status == "ready"
    assert plan.queries == (
        "paramagnetic nmr software",
        "pcs tensor fitting",
    )

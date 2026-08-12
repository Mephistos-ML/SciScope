"""AI planner tests."""

from __future__ import annotations

from app import config
from app.models.ai import AiSearchPlan, AiSourcePlan
from app.services.ai_planner import build_ai_search_plan


def test_build_ai_search_plan_returns_pending_plan_in_bootstrap_mode() -> None:
    plan = build_ai_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="repositories",
    )

    assert plan.search_scope == "repositories"
    assert plan.status == "pending"
    assert len(plan.source_plans) == 1
    assert plan.source_plans[0].source_type == "repositories"
    assert plan.source_plans[0].queries == ()


def test_build_ai_search_plan_preserves_requested_scope() -> None:
    plan = build_ai_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="all",
    )

    assert plan.search_scope == "all"


def test_build_ai_search_plan_uses_openai_planner_when_mode_is_openai(
    monkeypatch,
) -> None:
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")

    def _build_search_plan(_self, **kwargs) -> AiSearchPlan:
        assert kwargs["topic_description"] == "Paramagnetic NMR analysis workflows"
        assert kwargs["search_scope"] == "repositories"
        return AiSearchPlan(
            search_scope="repositories",
            status="ready",
            source_plans=(
                AiSourcePlan(
                    source_type="repositories",
                    queries=("paramagnetic nmr software", "pcs tensor fitting"),
                ),
            ),
        )

    monkeypatch.setattr(
        "app.services.ai_planner.OpenAiSearchPlanner.build_search_plan",
        _build_search_plan,
    )

    plan = build_ai_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="repositories",
    )

    assert plan.status == "ready"
    assert plan.source_plans[0].queries == (
        "paramagnetic nmr software",
        "pcs tensor fitting",
    )

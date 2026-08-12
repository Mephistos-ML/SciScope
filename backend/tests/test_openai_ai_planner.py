"""OpenAI-backed planner tests."""

from __future__ import annotations

from app.services.openai_ai_planner import OpenAiSearchPlanner


def test_openai_planner_uses_override_queries_without_model_call() -> None:
    planner = OpenAiSearchPlanner()

    plan = planner.build_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="repositories",
        override_queries=("pcs tensor fitting", "  paramagnetic nmr workflows "),
    )

    assert plan.status == "ready"
    assert plan.source_plans[0].queries == (
        "pcs tensor fitting",
        "paramagnetic nmr workflows",
    )

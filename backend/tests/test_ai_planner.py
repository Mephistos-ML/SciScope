"""AI planner tests."""

from __future__ import annotations

from app.services.ai_planner import build_ai_search_plan


def test_build_ai_search_plan_returns_pending_plan_without_override_queries() -> None:
    plan = build_ai_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="repositories",
    )

    assert plan.search_scope == "repositories"
    assert plan.status == "pending"
    assert len(plan.source_plans) == 1
    assert plan.source_plans[0].source_type == "repositories"
    assert plan.source_plans[0].queries == ()


def test_build_ai_search_plan_returns_ready_plan_with_override_queries() -> None:
    plan = build_ai_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="repositories",
        override_queries=(
            "pcs tensor fitting",
            "pcs tensor fitting",
            "  paramagnetic nmr   workflows  ",
        ),
    )

    assert plan.search_scope == "repositories"
    assert plan.status == "ready"
    assert len(plan.source_plans) == 1
    assert plan.source_plans[0].queries == (
        "pcs tensor fitting",
        "paramagnetic nmr workflows",
    )


def test_build_ai_search_plan_preserves_requested_scope() -> None:
    plan = build_ai_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="all",
    )

    assert plan.search_scope == "all"

"""OpenAI-backed planner tests."""

from __future__ import annotations

import pytest

from app.services.openai_client import OpenAIResponseError
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


def test_openai_planner_builds_plan_from_model_response(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.openai_ai_planner.build_openai_json_response",
        lambda **_: {
            "searchScope": "repositories",
            "sourcePlans": [
                {
                    "sourceType": "repositories",
                    "queries": [
                        "paramagnetic nmr software",
                        "pcs tensor fitting",
                        "paramagnetic nmr software",
                    ],
                }
            ],
        },
    )

    plan = planner.build_search_plan(
        topic_description="Paramagnetic NMR analysis workflows",
        search_scope="repositories",
    )

    assert plan.status == "ready"
    assert plan.source_plans[0].queries == (
        "paramagnetic nmr software",
        "pcs tensor fitting",
    )


def test_openai_planner_rejects_scope_drift(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.openai_ai_planner.build_openai_json_response",
        lambda **_: {
            "searchScope": "all",
            "sourcePlans": [
                {
                    "sourceType": "repositories",
                    "queries": ["paramagnetic nmr software"],
                }
            ],
        },
    )

    with pytest.raises(RuntimeError, match="changed the requested searchScope"):
        planner.build_search_plan(
            topic_description="Paramagnetic NMR analysis workflows",
            search_scope="repositories",
        )


def test_openai_planner_raises_for_invalid_payload(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.openai_ai_planner.build_openai_json_response",
        lambda **_: {
            "searchScope": "repositories",
            "sourcePlans": "not-a-list",
        },
    )

    with pytest.raises(RuntimeError, match="invalid sourcePlans"):
        planner.build_search_plan(
            topic_description="Paramagnetic NMR analysis workflows",
            search_scope="repositories",
        )

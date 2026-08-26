"""OpenAI-backed planner tests."""

from __future__ import annotations

import pytest

from app.services.ai.openai_planner import OpenAiSearchPlanner


def test_openai_planner_builds_plan_from_model_response(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()
    captured_prompts: dict[str, str] = {}

    def _fake_response(**kwargs):
        captured_prompts["system"] = kwargs["system_prompt"]
        captured_prompts["user"] = kwargs["user_prompt"]
        return {
            "queries": [
                "paramagnetic nmr software",
                "pcs tensor fitting",
                "lanthanide pcs",
                "magnetic susceptibility tensor",
                "pseudocontact shift",
                "pcs analysis",
                "paramagnetic restraints",
                "nmr tensor fitting",
                "lanthanide nmr",
                "paramagnetic structure refinement",
            ],
        }

    monkeypatch.setattr(
        "app.services.ai.openai_planner.build_openai_json_response",
        _fake_response,
    )

    plan = planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")

    assert plan.status == "ready"
    assert plan.queries == (
        "paramagnetic nmr software",
        "pcs tensor fitting",
        "lanthanide pcs",
        "magnetic susceptibility tensor",
        "pseudocontact shift",
        "pcs analysis",
        "paramagnetic restraints",
        "nmr tensor fitting",
        "lanthanide nmr",
        "paramagnetic structure refinement",
    )
    assert "scientific software discovery" in captured_prompts["system"]
    assert "Generate exactly 10 search queries." in captured_prompts["system"]
    assert "Every query must preserve at least one scientific anchor" in captured_prompts["system"]
    assert '"workflow", "pipeline", "Python"' in captured_prompts["system"]
    assert "Use multiple narrow scientific entry points" in captured_prompts["user"]
    assert "used for repository search and code search" in captured_prompts["user"]


def test_openai_planner_limits_normalized_query_count_to_ten(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.ai.openai_planner.build_openai_json_response",
        lambda **_: {
            "queries": [
                "query 1",
                "query 2",
                "query 3",
                "query 4",
                "query 5",
                "query 6",
                "query 7",
                "query 8",
                "query 9",
                "query 10",
                "query 11",
            ],
        },
    )

    plan = planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")

    assert plan.queries == (
        "query 1",
        "query 2",
        "query 3",
        "query 4",
        "query 5",
        "query 6",
        "query 7",
        "query 8",
        "query 9",
        "query 10",
    )


def test_openai_planner_raises_when_normalized_queries_are_not_exactly_ten(
    monkeypatch,
) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.ai.openai_planner.build_openai_json_response",
        lambda **_: {
            "queries": [
                "query 1",
                "query 1",
                "query 2",
                "query 3",
                "query 4",
                "query 5",
                "query 6",
                "query 7",
                "query 8",
                "query 9",
            ],
        },
    )

    with pytest.raises(RuntimeError, match="exactly 10 unique queries"):
        planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")


def test_openai_planner_raises_for_invalid_payload(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.ai.openai_planner.build_openai_json_response",
        lambda **_: {
            "queries": "not-a-list",
        },
    )

    with pytest.raises(RuntimeError, match="invalid queries"):
        planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")

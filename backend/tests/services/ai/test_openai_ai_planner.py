"""OpenAI-backed planner tests."""

from __future__ import annotations

import pytest

from app.services.ai.openai.planner import OpenAiSearchPlanner


def test_openai_planner_builds_plan_from_model_response(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()
    captured_prompts: dict[str, str] = {}

    def _fake_response(**kwargs):
        captured_prompts["system"] = kwargs["system_prompt"]
        captured_prompts["user"] = kwargs["user_prompt"]
        return {
            "queries": [
                "paramagnetic nmr",
                "pcs tensor fitting",
                "lanthanide pcs",
                "magnetic susceptibility tensor",
                "pseudocontact shift",
            ],
        }

    monkeypatch.setattr(
        "app.services.ai.openai.planner.build_openai_json_response",
        _fake_response,
    )

    plan = planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")

    assert plan.status == "ready"
    assert plan.queries == (
        "paramagnetic nmr",
        "pcs tensor fitting",
        "lanthanide pcs",
        "magnetic susceptibility tensor",
        "pseudocontact shift",
    )
    assert "scientific software repository discovery" in captured_prompts["system"]
    assert "Generate exactly 5 search queries" in captured_prompts["system"]
    assert "canonical short form of the topic" in captured_prompts["system"]
    assert "Do not invent software names" in captured_prompts["system"]
    assert captured_prompts["user"].startswith("Topic description:\n")


def test_openai_planner_limits_normalized_query_count_to_five(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.ai.openai.planner.build_openai_json_response",
        lambda **_: {
            "queries": [
                "query 1",
                "query 2",
                "query 3",
                "query 4",
                "query 5",
                "query 6",
                "query 7",
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
    )


def test_openai_planner_raises_when_normalized_queries_are_below_minimum(
    monkeypatch,
) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.ai.openai.planner.build_openai_json_response",
        lambda **_: {
            "queries": [
                "query 1",
                "query 1",
                "query 2",
            ],
        },
    )

    with pytest.raises(RuntimeError, match="5 unique queries"):
        planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")


def test_openai_planner_raises_for_invalid_payload(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()

    monkeypatch.setattr(
        "app.services.ai.openai.planner.build_openai_json_response",
        lambda **_: {
            "queries": "not-a-list",
        },
    )

    with pytest.raises(RuntimeError, match="invalid queries"):
        planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")

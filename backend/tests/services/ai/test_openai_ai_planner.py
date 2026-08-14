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
                "paramagnetic nmr software",
                "  pcs tensor fitting  ",
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
    )
    assert "scientific software discovery" in captured_prompts["system"]
    assert "Prefer 2-term queries." in captured_prompts["system"]
    assert '"workflow", "pipeline", "Python"' in captured_prompts["system"]
    assert "Do not return only ultra-specific jargon." in captured_prompts["user"]
    assert "used only for repository search" in captured_prompts["user"]


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

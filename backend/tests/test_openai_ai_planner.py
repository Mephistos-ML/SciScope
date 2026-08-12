"""OpenAI-backed planner tests."""

from __future__ import annotations

import pytest

from app.services.openai_ai_planner import OpenAiSearchPlanner


def test_openai_planner_builds_plan_from_model_response(monkeypatch) -> None:
    planner = OpenAiSearchPlanner()
    captured_prompts: dict[str, str] = {}

    def _fake_response(**kwargs):
        captured_prompts["system"] = kwargs["system_prompt"]
        captured_prompts["user"] = kwargs["user_prompt"]
        return {
            "searchScope": "repositories",
            "sourcePlans": [
                {
                    "sourceType": "repositories",
                    "queries": [
                        "paramagnetic nmr software",
                        "pcs tensor fitting",
                        "paramagnetic nmr software",
                        "  pcs tensor fitting  ",
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        "app.services.openai_ai_planner.build_openai_json_response",
        _fake_response,
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
    assert "controlled broadening" in captured_prompts["system"]
    assert "Do not return only ultra-specific jargon." in captured_prompts["user"]


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

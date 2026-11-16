# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""OpenAI-backed planner tests."""

from __future__ import annotations

import pytest

from app.integrations.ai.openai.planner import OpenAiSearchPlanner


def test_explicit_research_prompt_preserves_schema_and_production_default(monkeypatch):
    from app.integrations.ai.openai.planner import build_search_plan_request

    baseline = build_search_plan_request(topic_description="satellite data")
    captured = []

    def respond(**kwargs):
        captured.append(kwargs)
        return {"queries": ["satellite data", "Earth observation", "data catalog"]}

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response", respond
    )
    planner = OpenAiSearchPlanner(
        api_key="test",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test",
        reasoning_effort="low",
    )
    planner.build_search_plan(
        topic_description="satellite data", system_prompt="Frozen research prompt"
    )
    planner.build_search_plan(topic_description="satellite data")
    assert captured[0]["system_prompt"] == "Frozen research prompt"
    assert captured[1]["system_prompt"] == baseline.system_prompt
    assert (
        captured[0]["user_prompt"] == captured[1]["user_prompt"] == baseline.user_prompt
    )
    assert (
        captured[0]["json_schema"] == captured[1]["json_schema"] == baseline.json_schema
    )


@pytest.mark.parametrize("prompt", ["", "  ", "x" * (16 * 1024 + 1)])
def test_invalid_research_prompt_rejected_before_provider(monkeypatch, prompt):
    def network(**kwargs):
        pytest.fail("Invalid prompt must not trigger provider IO")

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response", network
    )
    planner = OpenAiSearchPlanner(
        api_key="test",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test",
        reasoning_effort="low",
    )
    with pytest.raises(ValueError, match="Research system prompt"):
        planner.build_search_plan(
            topic_description="satellite data", system_prompt=prompt
        )


def test_openai_planner_builds_plan_from_model_response(monkeypatch) -> None:
    planner = OpenAiSearchPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test-model",
        reasoning_effort="low",
    )
    captured_prompts: dict[str, str] = {}

    def _fake_response(**kwargs):
        captured_prompts["system"] = kwargs["system_prompt"]
        captured_prompts["user"] = kwargs["user_prompt"]
        return {
            "queries": [
                "paramagnetic nmr",
                "pcs tensor fitting",
                "lanthanide pcs",
            ],
        }

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response",
        _fake_response,
    )

    plan = planner.build_search_plan(
        topic_description="Paramagnetic NMR analysis workflows"
    )

    assert plan.status == "ready"
    assert plan.queries == (
        "paramagnetic nmr",
        "pcs tensor fitting",
        "lanthanide pcs",
    )
    assert captured_prompts["system"].strip()
    assert (
        captured_prompts["user"]
        == "Topic description:\nParamagnetic NMR analysis workflows"
    )


def test_openai_planner_rejects_unexpected_query_count(monkeypatch) -> None:
    planner = OpenAiSearchPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test-model",
        reasoning_effort="low",
    )

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response",
        lambda **_: {
            "queries": [
                "query 1",
                "query 2",
                "query 3",
                "query 4",
            ],
        },
    )

    with pytest.raises(RuntimeError, match="3 nonempty bounded string queries"):
        planner.build_search_plan(
            topic_description="Paramagnetic NMR analysis workflows"
        )


def test_openai_planner_raises_when_normalized_queries_are_below_minimum(
    monkeypatch,
) -> None:
    planner = OpenAiSearchPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test-model",
        reasoning_effort="low",
    )

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response",
        lambda **_: {
            "queries": [
                "query 1",
                "query 1",
                "query 2",
            ],
        },
    )

    with pytest.raises(RuntimeError, match="3 unique queries"):
        planner.build_search_plan(
            topic_description="Paramagnetic NMR analysis workflows"
        )


def test_openai_planner_raises_for_invalid_payload(monkeypatch) -> None:
    planner = OpenAiSearchPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test-model",
        reasoning_effort="low",
    )

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response",
        lambda **_: {
            "queries": "not-a-list",
        },
    )

    with pytest.raises(RuntimeError, match="invalid queries"):
        planner.build_search_plan(
            topic_description="Paramagnetic NMR analysis workflows"
        )


@pytest.mark.parametrize(
    "queries",
    [
        [1, "second", "third"],
        [None, "second", "third"],
        ["first", "FIRST", "third"],
        ["", "second", "third"],
        ["x" * 186, "second", "third"],
    ],
)
def test_untrusted_queries_cannot_become_an_execution_plan(monkeypatch, queries):
    from app.models.ai import AiResponseError

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response",
        lambda **_: {"queries": queries},
    )
    planner = OpenAiSearchPlanner(
        api_key="secret",
        base_url="https://example.test",
        timeout_seconds=2,
        model="test",
        reasoning_effort="low",
    )
    with pytest.raises(AiResponseError):
        planner.build_search_plan(topic_description="scientific topic")
    assert "secret" not in repr(planner)


@pytest.mark.parametrize("length", [185, 186])
def test_generated_query_length_is_enforced_before_normalization(monkeypatch, length):
    from app.models.ai import AiResponseError

    query = "x" * length
    captured = {}

    def response(**kwargs):
        captured.update(kwargs)
        return {"queries": [query, "second", "third"]}

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response", response
    )
    planner = OpenAiSearchPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test-model",
        reasoning_effort="low",
    )
    # The limit applies to generated queries, not the input scientific question.
    topic = "scientific requirement " * 30
    if length == 185:
        assert planner.build_search_plan(topic_description=topic).queries == (
            query,
            "second",
            "third",
        )
    else:
        with pytest.raises(AiResponseError, match="bounded string queries"):
            planner.build_search_plan(topic_description=topic)
    assert captured["user_prompt"] == f"Topic description:\n{topic.strip()}"
    schema = captured["json_schema"]["properties"]["queries"]
    assert schema["items"]["maxLength"] == 185
    assert schema["minItems"] == schema["maxItems"] == 3
    assert "at most 185 characters, including spaces" in captured["system_prompt"]


def test_whitespace_does_not_hide_an_overlength_generated_query(monkeypatch):
    from app.models.ai import AiResponseError

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response",
        lambda **_: {"queries": ["x" * 185 + " ", "second", "third"]},
    )
    planner = OpenAiSearchPlanner(
        api_key="test-key",
        base_url="https://example.test/v1",
        timeout_seconds=20,
        model="test-model",
        reasoning_effort="low",
    )
    with pytest.raises(AiResponseError, match="bounded string queries"):
        planner.build_search_plan(topic_description="scientific topic")


def test_rendered_request_matches_provider_input_and_schema_is_isolated(
    monkeypatch,
) -> None:
    from app.integrations.ai.openai.planner import build_search_plan_request

    topic = "Scientific domain: Earth science\n\nHow do I find satellite data?"
    preview = build_search_plan_request(topic_description=topic)
    captured = {}

    def response(**kwargs):
        captured.update(kwargs)
        return {"queries": ["satellite data", "Earth observation", "data catalog"]}

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.build_openai_json_response", response
    )
    planner = OpenAiSearchPlanner(
        api_key="offline",
        base_url="https://example.test",
        timeout_seconds=20,
        model="test",
        reasoning_effort="low",
    )
    planner.build_search_plan(topic_description=topic)
    assert (
        captured["user_prompt"] == preview.user_prompt == f"Topic description:\n{topic}"
    )
    assert captured["system_prompt"] == preview.system_prompt
    assert captured["json_schema"] == preview.json_schema
    preview.json_schema.clear()
    fresh = build_search_plan_request(topic_description=topic)
    assert fresh.json_schema["properties"]["queries"]["minItems"] == 3

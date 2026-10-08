"""OpenAI raw client response parsing tests."""

from __future__ import annotations

import httpx2 as httpx
import pytest

from app.models.ai import AiResponseError
from app.integrations.ai.openai.client import (
    build_openai_json_response,
)


def test_openai_client_parses_text_from_output_content(monkeypatch) -> None:

    captured_request: dict[str, object] = {}

    def fake_post(self: httpx.Client, url: str, json: dict[str, object]) -> httpx.Response:
        captured_request.update(json)
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                "content": [
                            {
                                "type": "output_text",
                                "text": '{"queries":[]}',
                            }
                        ],
                    }
                ]
            },
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    payload = build_openai_json_response(
        api_key="test-key", base_url="https://api.openai.com/v1", timeout_seconds=20,
        model="gpt-5-mini",
        reasoning_effort="low",
        system_prompt="system",
        user_prompt="user",
        json_schema={"type": "object"},
    )

    assert payload == {"queries": []}
    assert captured_request["reasoning"] == {"effort": "low"}


def test_openai_client_rejects_missing_output_text(monkeypatch) -> None:

    def fake_post(self: httpx.Client, url: str, json: dict[str, object]) -> httpx.Response:
        return httpx.Response(
            200,
            json={"output": [{"type": "message", "content": []}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(AiResponseError, match="did not include output text"):
        build_openai_json_response(
            api_key="test-key", base_url="https://api.openai.com/v1", timeout_seconds=20,
        model="gpt-5-mini",
            reasoning_effort="low",
            system_prompt="system",
            user_prompt="user",
            json_schema={"type": "object"},
        )


@pytest.mark.parametrize("failure_kind", ["timeout", "http", "invalid_json", "invalid_root", "invalid_output"])
def test_planner_protocol_failures_are_application_errors(monkeypatch, failure_kind):
    from app.models.ai import AiDependencyError

    def post(*args, **kwargs):
        if failure_kind == "timeout":
            raise httpx.ReadTimeout("private diagnostics")
        request = httpx.Request("POST", "https://example.test/responses")
        if failure_kind == "http":
            return httpx.Response(429, text="private credentials", request=request)
        if failure_kind == "invalid_json":
            return httpx.Response(200, text="invalid json", request=request)
        if failure_kind == "invalid_root":
            return httpx.Response(200, json=[], request=request)
        return httpx.Response(200, json={"output_text": "not json"}, request=request)

    monkeypatch.setattr(httpx.Client, "post", post)
    with pytest.raises(AiDependencyError) as failure:
        build_openai_json_response(
            api_key="test-key", base_url="https://example.test", timeout_seconds=2,
            model="test", reasoning_effort="low", system_prompt="system",
            user_prompt="topic", json_schema={"type": "object"},
        )
    assert "private" not in str(failure.value)
    if failure_kind != "invalid_root":
        assert failure.value.__cause__ is not None

"""OpenAI raw client response parsing tests."""

from __future__ import annotations

import httpx2 as httpx
import pytest

from app import config
from app.services.ai.openai_client import (
    OpenAIResponseError,
    build_openai_json_response,
)


def test_openai_client_parses_text_from_output_content(monkeypatch) -> None:
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(config, "OPENAI_TIMEOUT_SECONDS", 20.0)

    def fake_post(self: httpx.Client, url: str, json: dict[str, object]) -> httpx.Response:
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
        model="gpt-5-mini",
        system_prompt="system",
        user_prompt="user",
        json_schema={"type": "object"},
    )

    assert payload == {"queries": []}


def test_openai_client_rejects_missing_output_text(monkeypatch) -> None:
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(config, "OPENAI_TIMEOUT_SECONDS", 20.0)

    def fake_post(self: httpx.Client, url: str, json: dict[str, object]) -> httpx.Response:
        return httpx.Response(
            200,
            json={"output": [{"type": "message", "content": []}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(OpenAIResponseError, match="did not include output text"):
        build_openai_json_response(
            model="gpt-5-mini",
            system_prompt="system",
            user_prompt="user",
            json_schema={"type": "object"},
        )

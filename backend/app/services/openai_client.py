"""Minimal OpenAI Responses API client for server-side planning."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app import config


class OpenAIClientConfigurationError(RuntimeError):
    """Raised when OpenAI client settings are incomplete."""


class OpenAIResponseError(RuntimeError):
    """Raised when OpenAI returns an invalid planner response."""


def build_openai_json_response(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],
) -> dict[str, Any]:
    """Create one structured JSON response through the OpenAI Responses API."""

    if not config.OPENAI_API_KEY:
        raise OpenAIClientConfigurationError(
            "Missing required environment variable: OPENAI_API_KEY"
        )

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": system_prompt,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_prompt,
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "sciscope_ai_search_plan",
                "schema": json_schema,
                "strict": True,
            }
        },
    }

    with httpx.Client(
        base_url=config.OPENAI_BASE_URL.rstrip("/"),
        timeout=config.OPENAI_TIMEOUT_SECONDS,
        headers={
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    ) as client:
        response = client.post("/responses", json=payload)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenAIResponseError(
            f"OpenAI request failed with status {exc.response.status_code}"
        ) from exc

    data = response.json()
    output_text = data.get("output_text")
    if not isinstance(output_text, str) or not output_text.strip():
        raise OpenAIResponseError("OpenAI response did not include output_text")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseError("OpenAI response returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise OpenAIResponseError("OpenAI response JSON root must be an object")
    return parsed

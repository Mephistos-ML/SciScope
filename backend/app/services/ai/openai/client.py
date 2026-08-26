"""Minimal OpenAI Responses API client for server-side planning."""

from __future__ import annotations

import json
from typing import Any

import httpx2 as httpx

from app import config


class OpenAIClientConfigurationError(RuntimeError):
    """Raised when OpenAI client settings are incomplete."""


class OpenAIResponseError(RuntimeError):
    """Raised when OpenAI returns an invalid planner response."""


def _extract_response_text(data: dict[str, Any]) -> str:
    """Extract the first text payload from a raw Responses API response."""

    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output_items = data.get("output")
    if not isinstance(output_items, list):
        raise OpenAIResponseError("OpenAI response did not include output text")

    for output_item in output_items:
        if not isinstance(output_item, dict):
            continue

        content_items = output_item.get("content")
        if not isinstance(content_items, list):
            continue

        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue

            text_value = content_item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                return text_value

    raise OpenAIResponseError("OpenAI response did not include output text")


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
        response_preview = exc.response.text.strip()
        if len(response_preview) > 1000:
            response_preview = f"{response_preview[:1000]}..."
        raise OpenAIResponseError(
            "OpenAI request failed with status "
            f"{exc.response.status_code}: {response_preview or '<empty response>'}"
        ) from exc

    data = response.json()
    output_text = _extract_response_text(data)

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseError("OpenAI response returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise OpenAIResponseError("OpenAI response JSON root must be an object")
    return parsed

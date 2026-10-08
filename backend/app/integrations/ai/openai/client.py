"""Minimal OpenAI Responses API client for server-side planning."""

from __future__ import annotations

import json
from typing import Any

import httpx2 as httpx

from app.models.ai import AiConfigurationError, AiDependencyError, AiResponseError


def _extract_response_text(data: dict[str, Any]) -> str:
    """Extract the first text payload from a raw Responses API response."""

    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output_items = data.get("output")
    if not isinstance(output_items, list):
        raise AiResponseError("OpenAI response did not include output text")

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

    raise AiResponseError("OpenAI response did not include output text")


def build_openai_json_response(
    *,
    api_key: str,
    base_url: str,
    timeout_seconds: float,
    model: str,
    reasoning_effort: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],
) -> dict[str, Any]:
    """Create one structured JSON response through the OpenAI Responses API."""

    if not api_key:
        raise AiConfigurationError(
            "Missing required environment variable: OPENAI_API_KEY"
        )

    payload = {
        "model": model,
        "reasoning": {"effort": reasoning_effort},
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

    try:
        with httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        ) as client:
            response = client.post("/responses", json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise AiDependencyError(f"AI request failed with status {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise AiDependencyError("AI request could not be completed.") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise AiResponseError("AI response returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise AiResponseError("AI response root must be an object.")
    output_text = _extract_response_text(data)

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise AiResponseError("OpenAI response returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise AiResponseError("OpenAI response JSON root must be an object")
    return parsed

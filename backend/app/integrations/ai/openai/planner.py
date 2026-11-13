# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""OpenAI-backed AI search planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.ai import AiSearchPlan
from app.integrations.ai.openai.client import build_openai_json_response
from app.models.ai import normalize_search_queries
from app.models.ai import AiResponseError

SEARCH_QUERY_COUNT = 3
MAX_GENERATED_QUERY_LENGTH = 185

_SEARCH_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["queries"],
    "properties": {
        "queries": {
            "type": "array",
            "minItems": SEARCH_QUERY_COUNT,
            "maxItems": SEARCH_QUERY_COUNT,
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_GENERATED_QUERY_LENGTH,
            },
        },
    },
}

_SYSTEM_PROMPT = f"""Generate exactly 3 search queries for scientific software repositories
from the user's scientific question.

Each query will be searched as a quoted phrase. Prefer short expressions
likely to appear verbatim in source code or documentation.

Rules:
- Preserve the scientific meaning and explicitly named entities.
- Prefer 2-3 words per query. Use up to 4 to preserve a scientific name.
- A single explicitly named tool or acronym is allowed.
- Choose distinct, complementary phrases: a named tool, a scientific
  concept, or an established synonym supported by the question.
- Reordering words or adding generic filler does not create a distinct query.
- Include explicit language, environment, or artifact requirements where
  they form a natural search phrase; do not combine every requirement
  into one query.
- Do not invent instruments, methods, software names, or restrictions.
- Do not add generic words such as software, tool, library, tutorial,
  examples, or workflow merely to make a query longer.
- If the question is ambiguous, retain its ambiguity.
- Use ASCII text without quotation marks or search operators.
- Each query must contain at most {MAX_GENERATED_QUERY_LENGTH} characters, including spaces.
- Return only JSON matching the provided schema.
"""


@dataclass(frozen=True)
class OpenAiSearchPlanner:
    """Planner implementation backed by OpenAI."""

    api_key: str = field(repr=False)
    base_url: str
    timeout_seconds: float
    model: str
    reasoning_effort: str

    def build_search_plan(
        self,
        *,
        topic_description: str,
    ) -> AiSearchPlan:
        user_prompt = _build_user_prompt(
            topic_description=topic_description,
        )
        payload = build_openai_json_response(
            api_key=self.api_key, base_url=self.base_url, timeout_seconds=self.timeout_seconds,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_schema=_SEARCH_PLAN_JSON_SCHEMA,
        )
        return _parse_ai_search_plan(payload)


def _build_user_prompt(
    *,
    topic_description: str,
) -> str:
    return f"Topic description:\n{topic_description.strip() or 'Untitled topic'}"


def _parse_ai_search_plan(
    payload: dict[str, Any],
) -> AiSearchPlan:
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list):
        raise AiResponseError("OpenAI planner returned invalid queries")

    if len(raw_queries) != SEARCH_QUERY_COUNT or any(
        not isinstance(query, str)
        or not query.strip()
        or len(query) > MAX_GENERATED_QUERY_LENGTH
        for query in raw_queries
    ):
        raise AiResponseError(
            "AI planner must return 3 nonempty bounded string queries "
            f"(at most {MAX_GENERATED_QUERY_LENGTH} characters each)"
        )
    queries = normalize_search_queries(raw_queries)
    if len(queries) != SEARCH_QUERY_COUNT:
        raise AiResponseError("OpenAI planner must return 3 unique queries")

    return AiSearchPlan(
        status="ready",
        queries=queries,
    )

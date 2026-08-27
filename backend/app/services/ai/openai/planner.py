"""OpenAI-backed AI search planner."""

from __future__ import annotations

from typing import Any

from app import config
from app.models.ai import AiSearchPlan
from app.services.ai.openai.client import build_openai_json_response
from app.services.ai.search_plans import normalize_search_queries

MIN_SEARCH_QUERY_COUNT = 3
TARGET_SEARCH_QUERY_COUNT = 5
MAX_SEARCH_QUERY_COUNT = 6

_SEARCH_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["queries"],
    "properties": {
        "queries": {
            "type": "array",
            "minItems": MIN_SEARCH_QUERY_COUNT,
            "maxItems": MAX_SEARCH_QUERY_COUNT,
            "items": {
                "type": "string",
            },
        },
    },
}

_SYSTEM_PROMPT = """Generate 3 to 6 GitHub search queries for scientific software discovery.

Goal: find repositories implementing the described scientific method or software capability.

Rules:
- Return only JSON matching the provided schema.
- Aim for 5 queries when possible.
- Prefer narrow scientific queries over broad generic ones.
- Each query must add a new retrieval angle.
- Do not repeat the same phrase with minor rewording.
- Avoid generic software terms unless tied to the scientific context.
- Prefer short technical phrases, not full sentences.
- Use these angles when possible:
  1. host software
  2. exact method
  3. scientific synonym
  4. implementation term
  5. alternate domain phrase
  6. optional extra query only if it is clearly distinct
"""


class OpenAiSearchPlanner:
    """Planner implementation backed by OpenAI."""

    def build_search_plan(
        self,
        *,
        topic_description: str,
    ) -> AiSearchPlan:
        user_prompt = _build_user_prompt(
            topic_description=topic_description,
        )
        payload = build_openai_json_response(
            model=config.OPENAI_MODEL,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_schema=_SEARCH_PLAN_JSON_SCHEMA,
        )
        return _parse_ai_search_plan(payload)


def _build_user_prompt(
    *,
    topic_description: str,
) -> str:
    return (
        "Topic description:\n"
        f"{topic_description.strip() or 'Untitled topic'}"
    )


def _parse_ai_search_plan(
    payload: dict[str, Any],
) -> AiSearchPlan:
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list):
        raise RuntimeError("OpenAI planner returned invalid queries")

    queries = normalize_search_queries(str(raw_query) for raw_query in raw_queries)[
        :MAX_SEARCH_QUERY_COUNT
    ]
    if not MIN_SEARCH_QUERY_COUNT <= len(queries) <= MAX_SEARCH_QUERY_COUNT:
        raise RuntimeError("OpenAI planner must return 3 to 6 unique queries")

    return AiSearchPlan(
        status="ready" if queries else "pending",
        queries=queries,
    )

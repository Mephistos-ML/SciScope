"""OpenAI-backed AI search planner."""

from __future__ import annotations

from typing import Any

from app import config
from app.models.ai import AiSearchPlan
from app.services.ai.openai.client import build_openai_json_response
from app.services.ai.search_plans import normalize_search_queries

SEARCH_QUERY_COUNT = 5

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
            },
        },
    },
}

_SYSTEM_PROMPT = """Generate exactly 5 search queries for scientific software repository discovery.

Goal: maximize recall of domain-specific scientific software repositories while avoiding generic software, papers, datasets, tutorials, and unrelated tools.

Rules:
- Query 1 must be the canonical short form of the topic.
- Stay close to the user topic and preserve its scientific meaning.
- Do not invent software names, package names, frameworks, languages, or file names that are not explicitly mentioned in the topic.
- Do not add a programming language unless it is explicitly mentioned in the topic.
- Each query must represent a meaningfully different retrieval angle, not a minor rewording.
- Prefer exact scientific method names, scientific subterms, implementation phrases, and domain-specific terminology that are likely to appear in repository metadata or code search.
- Keep queries short: 2 to 6 words.
- Avoid broad generic terms like: software, tool, analysis, project, model, python, dataset, paper, tutorial, notes, example.
- Use only ASCII characters.
- Return only JSON matching the provided schema.

Use these retrieval angles when possible:
  1. canonical topic phrase
  2. exact method or algorithm name
  3. domain-specific synonym or closely related scientific term
  4. implementation-oriented phrase
  5. alternate scientific phrasing that stays within the same topic
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
    return f"Topic description:\n{topic_description.strip() or 'Untitled topic'}"


def _parse_ai_search_plan(
    payload: dict[str, Any],
) -> AiSearchPlan:
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list):
        raise RuntimeError("OpenAI planner returned invalid queries")

    queries = normalize_search_queries(str(raw_query) for raw_query in raw_queries)[
        :SEARCH_QUERY_COUNT
    ]
    if len(queries) != SEARCH_QUERY_COUNT:
        raise RuntimeError("OpenAI planner must return 5 unique queries")

    return AiSearchPlan(
        status="ready" if queries else "pending",
        queries=queries,
    )

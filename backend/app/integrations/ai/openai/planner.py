"""OpenAI-backed AI search planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.ai import AiSearchPlan
from app.integrations.ai.openai.client import build_openai_json_response
from app.models.ai import normalize_search_queries
from app.models.ai import AiResponseError

SEARCH_QUERY_COUNT = 3

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
                "maxLength": 500,
            },
        },
    },
}

_SYSTEM_PROMPT = """Generate exactly 3 ordered search queries for scientific software repository discovery.

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

Use these retrieval angles in this order:
  1. canonical topic phrase: the strongest first search for the user
  2. a substantially different method, synonym, or implementation-oriented angle
  3. another substantially different scientific phrasing that stays within the topic
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
        not isinstance(query, str) or not query.strip() or len(query) > 500
        for query in raw_queries
    ):
        raise AiResponseError("AI planner must return 3 nonempty bounded string queries")
    queries = normalize_search_queries(raw_queries)
    if len(queries) != SEARCH_QUERY_COUNT:
        raise AiResponseError("OpenAI planner must return 3 unique queries")

    return AiSearchPlan(
        status="ready",
        queries=queries,
    )

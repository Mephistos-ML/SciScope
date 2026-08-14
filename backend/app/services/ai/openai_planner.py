"""OpenAI-backed AI search planner."""

from __future__ import annotations

from typing import Any

from app import config
from app.models.ai import AiSearchPlan
from app.services.ai.openai_client import build_openai_json_response
from app.services.ai.search_plans import normalize_search_queries

_SEARCH_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["queries"],
    "properties": {
        "queries": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
}

_SYSTEM_PROMPT = """You are the query-planning engine for SciScope.

Turn one research topic description into a compact set of short technical search queries for scientific software discovery.

Rules:
- Return only JSON matching the provided schema.
- Generate 5 to 8 search queries.
- Prefer 2-term queries.
- Use 1-term or 3-term queries only when scientifically necessary.
- Avoid queries longer than 3 terms unless shortening would destroy the scientific meaning.
- Optimise for high recall.
- Each query must represent a distinct semantic entry point into the user's research topic.
- Queries should use terminology likely to appear in repository names, descriptions, README files, documentation, topics, or package metadata.
- Preserve important scientific concepts, methods, observables, calculations, and established abbreviations from the user's description.
- Include alternative terminology when it opens a meaningfully different retrieval path.
- Across the query set, cover a useful mix of:
  - core research domain
  - phenomena or observables
  - methods or calculations
  - computational tasks
  - established abbreviations or alternative terminology
- Prefer specific scientific terminology over generic software-related words.
- Do not add words such as "software", "tool", "package", "workflow", "pipeline", "Python", "GitHub", "GitLab", or "repository" unless they are genuinely central to the user's topic.
- Do not generate superficial variants of the same query.
- Do not generate long natural-language questions.
- Do not use source-specific operators or search syntax.
- Broaden enough to discover relevant software described using different terminology, but do not drift into adjacent research fields.
- The query planner should optimise recall; downstream ranking will handle precision.
- Do not include explanations.
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
        "Generate reusable repository search queries for this topic.\n"
        "Balance recall and specificity.\n"
        "Do not return only ultra-specific jargon.\n"
        "These queries will be used only for repository search.\n"
        "Topic description:\n"
        f"{topic_description.strip() or 'Untitled topic'}"
    )


def _parse_ai_search_plan(
    payload: dict[str, Any],
) -> AiSearchPlan:
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list):
        raise RuntimeError("OpenAI planner returned invalid queries")

    queries = normalize_search_queries(str(raw_query) for raw_query in raw_queries)

    return AiSearchPlan(
        status="ready" if queries else "pending",
        queries=queries,
    )

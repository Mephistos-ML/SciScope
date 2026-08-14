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

_SYSTEM_PROMPT = """You are planning reusable technical search queries for SciScope.

Turn one research topic description into source-agnostic search queries with high recall.

Rules:
- Return only JSON matching the provided schema.
- Generate queries only for repository discovery.
- Produce 4 to 7 concise repository search queries.
- Queries should be short, technical, and keyword-oriented.
- Queries must stay reusable across multiple source types such as repositories,
  papers, workshops, conferences, and technical news.
- Prefer source-agnostic domain phrases that can work in GitHub, Google, and other search systems.
- Use controlled broadening:
  - include 1 to 2 broad domain queries
  - include 2 to 3 method-level queries
  - include 1 to 2 software, pipeline, workflow, or python-oriented queries
- Start from the core domain and method terms from the topic.
- Preserve the user's intent, but broaden slightly for retrieval.
- Prefer common technical terms over rare expert-only phrasing.
- Avoid jumping too early into niche subtopics, vendor names, or very rare abbreviations
  unless they are clearly central in the user's description.
- Avoid source-specific operators, repo-only wording, or site-specific syntax.
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

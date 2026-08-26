"""OpenAI-backed AI search planner."""

from __future__ import annotations

from typing import Any

from app import config
from app.models.ai import AiSearchPlan
from app.services.ai.openai.client import build_openai_json_response
from app.services.ai.search_plans import normalize_search_queries

_SEARCH_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["queries"],
    "properties": {
        "queries": {
            "type": "array",
            "minItems": 10,
            "maxItems": 10,
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
- Generate exactly 10 search queries.
- Prefer 2-term or 3-term queries.
- Allow 4-term or 5-term queries when they preserve a canonical scientific phrase.
- Avoid queries longer than 5 terms unless shortening would destroy the scientific meaning.
- Optimise for high recall.
- Each query must represent a distinct semantic entry point into the user's research topic.
- Queries should use terminology likely to appear in repository names, descriptions, README files, documentation, topics, or package metadata.
- Preserve important scientific concepts, methods, observables, calculations, and established abbreviations from the user's description.
- Every query must preserve at least one scientific anchor from the topic description.
- Prefer queries that keep two scientific anchors when possible.
- Include alternative terminology when it opens a meaningfully different retrieval path.
- Across the query set, cover a useful mix of:
  - core research domain
  - phenomena or observables
  - methods or calculations
  - computational tasks
  - established abbreviations or alternative terminology
- Prefer specific scientific terminology over generic software-related words.
- Do not add words such as "software", "tool", "package", "workflow", "pipeline", "Python", "GitHub", "GitLab", or "repository" unless they are genuinely central to the user's topic.
- Do not emit broad standalone phrases that could match non-scientific repositories.
- Do not emit queries like "pair potential", "simulation", "correction", or "parser" unless they are anchored by a domain-specific scientific term.
- Do not emit source-specific syntax or implementation-specific tokens such as "pair_style" unless they are clearly part of how the scientific method is described in repositories.
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
        "Generate reusable scientific software search queries for this topic.\n"
        "Balance recall and specificity.\n"
        "Use multiple narrow scientific entry points instead of broad generic phrases.\n"
        "Do not return only ultra-specific jargon.\n"
        "These queries will be used for repository search and code search.\n"
        "Topic description:\n"
        f"{topic_description.strip() or 'Untitled topic'}"
    )


def _parse_ai_search_plan(
    payload: dict[str, Any],
) -> AiSearchPlan:
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list):
        raise RuntimeError("OpenAI planner returned invalid queries")

    queries = normalize_search_queries(str(raw_query) for raw_query in raw_queries)[:10]
    if len(queries) != 10:
        raise RuntimeError("OpenAI planner must return exactly 10 unique queries")

    return AiSearchPlan(
        status="ready" if queries else "pending",
        queries=queries,
    )

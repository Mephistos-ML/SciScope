"""OpenAI-backed AI search planner."""

from __future__ import annotations

from typing import Any, cast

from app import config
from app.models.ai import AiSearchPlan, AiSourcePlan, SearchScope
from app.services.ai_search_plans import normalize_search_queries
from app.services.openai_client import build_openai_json_response

_SEARCH_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["searchScope", "sourcePlans"],
    "properties": {
        "searchScope": {
            "type": "string",
            "enum": ["repositories", "all"],
        },
        "sourcePlans": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["sourceType", "queries"],
                "properties": {
                    "sourceType": {
                        "type": "string",
                        "enum": ["repositories"],
                    },
                    "queries": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                },
            },
        },
    },
}

_SYSTEM_PROMPT = """You are planning repository discovery queries for SciScope.

Turn one research topic description into repository search queries with high recall.

Rules:
- Return only JSON matching the provided schema.
- searchScope must match the requested scope from the user.
- For now, only produce sourcePlans for repositories.
- Produce 4 to 7 concise repository search queries.
- Queries should be short, technical, and keyword-oriented.
- Prefer repository-friendly search phrases that are likely to match project names,
  READMEs, code comments, docs, or package descriptions.
- Use controlled broadening:
  - include 1 to 2 broad domain queries
  - include 2 to 3 method-level queries
  - include 1 to 2 software, pipeline, workflow, or python-oriented queries
- Start from the core domain and method terms from the topic.
- Preserve the user's intent, but broaden slightly for retrieval.
- Prefer common technical terms over rare expert-only phrasing.
- Avoid jumping too early into niche subtopics, vendor names, or very rare abbreviations
  unless they are clearly central in the user's description.
- Do not include explanations.
- Do not invent sources other than repositories.
"""


class OpenAiSearchPlanner:
    """Planner implementation backed by OpenAI."""

    def build_search_plan(
        self,
        *,
        topic_description: str,
        search_scope: SearchScope,
    ) -> AiSearchPlan:
        user_prompt = _build_user_prompt(
            topic_description=topic_description,
            search_scope=search_scope,
        )
        payload = build_openai_json_response(
            model=config.OPENAI_MODEL,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_schema=_SEARCH_PLAN_JSON_SCHEMA,
        )
        return _parse_ai_search_plan(payload, requested_scope=search_scope)


def _build_user_prompt(
    *,
    topic_description: str,
    search_scope: SearchScope,
) -> str:
    return (
        f"Requested search scope: {search_scope}\n"
        "Generate repository search queries for this topic.\n"
        "Balance recall and specificity.\n"
        "Do not return only ultra-specific jargon.\n"
        "Topic description:\n"
        f"{topic_description.strip() or 'Untitled topic'}"
    )


def _parse_ai_search_plan(
    payload: dict[str, Any],
    *,
    requested_scope: SearchScope,
) -> AiSearchPlan:
    search_scope = payload.get("searchScope")
    if search_scope not in {"repositories", "all"}:
        raise RuntimeError("OpenAI planner returned an invalid searchScope")

    if search_scope != requested_scope:
        raise RuntimeError("OpenAI planner changed the requested searchScope")

    raw_source_plans = payload.get("sourcePlans")
    if not isinstance(raw_source_plans, list):
        raise RuntimeError("OpenAI planner returned invalid sourcePlans")

    source_plans: list[AiSourcePlan] = []
    for raw_source_plan in raw_source_plans:
        if not isinstance(raw_source_plan, dict):
            raise RuntimeError("OpenAI planner returned an invalid source plan")

        source_type = raw_source_plan.get("sourceType")
        if source_type != "repositories":
            raise RuntimeError("OpenAI planner returned an unsupported source type")

        raw_queries = raw_source_plan.get("queries")
        if not isinstance(raw_queries, list):
            raise RuntimeError("OpenAI planner returned invalid source queries")

        queries = normalize_search_queries(
            str(raw_query)
            for raw_query in raw_queries
        )
        source_plans.append(
            AiSourcePlan(
                source_type="repositories",
                queries=queries,
            )
        )

    return AiSearchPlan(
        search_scope=cast(SearchScope, search_scope),
        status=(
            "ready"
            if any(source_plan.queries for source_plan in source_plans)
            else "pending"
        ),
        source_plans=tuple(source_plans),
    )

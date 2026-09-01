"""Explore response-mode selection and shared response envelopes."""

from __future__ import annotations

from typing import Literal

from app import config
from app.services.search.explore.beta import build_beta_items
from app.services.search.explore.canonical import build_canonical_items
from app.services.search.explore.evaluation import ExploreSearchEvaluation

ExploreResponseMode = Literal["canonical", "beta"]


def build_explore_search_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    evaluation: ExploreSearchEvaluation,
    response_mode: ExploreResponseMode,
) -> dict[str, object]:
    """Project one shared evaluation into its requested response mode."""

    if response_mode == "beta":
        items = build_beta_items(evaluation)
    else:
        items = build_canonical_items(evaluation)

    payload = _build_response_envelope(
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        evaluation=evaluation,
        items=items,
    )
    if response_mode == "beta":
        payload["beta"] = {
            "enabled": True,
            "candidateCount": len(evaluation.ranking.ranked_candidates),
            "relevanceCutoff": evaluation.ranking.relevance_cutoff,
        }
    return payload


def build_empty_explore_search_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    response_mode: ExploreResponseMode,
) -> dict[str, object]:
    """Build an empty response when planning produces no repository queries."""

    payload: dict[str, object] = {
        "topicDescription": topic_description,
        "aiSearchPlan": dict(ai_search_plan_payload),
        "items": [],
        "sourceStatuses": [],
    }
    if response_mode == "beta":
        payload["beta"] = {
            "enabled": True,
            "candidateCount": 0,
            "relevanceCutoff": config.EXPLORE_SEARCH_RELEVANCE_CUTOFF,
        }
    return payload


def _build_response_envelope(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    evaluation: ExploreSearchEvaluation,
    items: list[dict[str, object]],
) -> dict[str, object]:
    retrieved = evaluation.retrieved
    return {
        "topicDescription": topic_description,
        "aiSearchPlan": dict(ai_search_plan_payload),
        "items": items,
        "sourceStatuses": list(retrieved.source_statuses),
        "partial": retrieved.partial,
        "message": _build_partial_message(retrieved.warnings) if retrieved.partial else None,
    }


def _build_partial_message(warnings: tuple[str, ...]) -> str | None:
    if not warnings:
        return "Search completed with partial coverage."

    visible_warnings = list(dict.fromkeys(warnings))
    summary = "; ".join(visible_warnings[:2])
    if len(visible_warnings) > 2:
        summary += f"; and {len(visible_warnings) - 2} more"
    return f"Search completed with partial coverage: {summary}"

"""Canonical product response envelopes for Explore searches."""

from __future__ import annotations

from app.services.search.explore.canonical import build_canonical_items
from app.services.search.explore.evaluation import ExploreSearchEvaluation


def build_explore_search_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    evaluation: ExploreSearchEvaluation,
    can_expand: bool = False,
) -> dict[str, object]:
    """Project an evaluation into the one public product representation."""

    return _build_response_envelope(
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        evaluation=evaluation,
        items=build_canonical_items(evaluation),
        can_expand=can_expand,
    )


def build_empty_explore_search_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    can_expand: bool = False,
) -> dict[str, object]:
    """Build an empty response when planning produces no repository queries."""

    payload: dict[str, object] = {
        "topicDescription": topic_description,
        "aiSearchPlan": _build_public_ai_search_plan(ai_search_plan_payload),
        "items": [],
        "sourceStatuses": [],
        "canExpand": can_expand,
    }
    return payload


def _build_response_envelope(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    evaluation: ExploreSearchEvaluation,
    items: list[dict[str, object]],
    can_expand: bool,
) -> dict[str, object]:
    retrieved = evaluation.retrieved
    return {
        "topicDescription": topic_description,
        "aiSearchPlan": _build_public_ai_search_plan(ai_search_plan_payload),
        "items": items,
        "sourceStatuses": list(retrieved.source_statuses),
        "partial": retrieved.partial,
        "message": _build_partial_message(retrieved.warnings) if retrieved.partial else None,
        "canExpand": can_expand,
    }


def _build_public_ai_search_plan(
    ai_search_plan_payload: dict[str, object],
) -> dict[str, object]:
    """Keep generated query text in the private durable report surface."""

    return {
        "status": ai_search_plan_payload.get("status", "pending"),
        "queries": [],
    }


def _build_partial_message(warnings: tuple[str, ...]) -> str | None:
    if not warnings:
        return "Search completed with partial coverage."

    visible_warnings = list(dict.fromkeys(warnings))
    summary = "; ".join(visible_warnings[:2])
    if len(visible_warnings) > 2:
        summary += f"; and {len(visible_warnings) - 2} more"
    return f"Search completed with partial coverage: {summary}"

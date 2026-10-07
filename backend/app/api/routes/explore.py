"""Explore search route."""

from __future__ import annotations

from fastapi import Request
from fastapi import HTTPException, status

from app.models.explore_access import ExploreTier
from app.services.auth.service import get_current_user
from app.services.security.turnstile import verify_turnstile_token
from app.services.search.access.errors import build_explore_access_denied_error
from app.services.search.access.policy import has_search_quota_bypass
from app.services.search.access.service import (
    build_turnstile_failure_decision,
    reserve_explore_access,
    hash_explore_topic,
    read_explore_client_ip,
    record_blocked_explore_attempt,
    resolve_explore_actor,
)
from app.services.search.explore.jobs import (
    create_explore_search_run,
    expand_explore_search_run,
    get_explore_search_run,
)
from app.services.search.explore.service import run_explore_search
from app.services.search.observability.context import SearchLogContext, build_request_id


def search_explore_response(
    request: Request,
    payload: dict[str, object],
) -> dict[str, object]:
    """Run an explore search from one topic description."""

    topic_description, topic_hash = _authorize_explore_search_request(
        request,
        payload,
    )
    return run_explore_search(
        topic_description=topic_description,
        database_url=request.app.state.database_url,
        log_context=SearchLogContext(
            request_id=build_request_id(),
            topic_hash=topic_hash,
        ),
    )


def create_explore_search_run_response(
    request: Request,
    payload: dict[str, object],
) -> dict[str, object]:
    """Create one background explore search run."""

    topic_description, topic_hash = _authorize_explore_search_request(
        request,
        payload,
    )
    user = get_current_user(request, database_url=request.app.state.database_url)
    return create_explore_search_run(
        topic_description=topic_description,
        owner_user_id=user.user_id if user else None,
        database_url=request.app.state.database_url,
    )


def get_explore_search_run_response(
    request: Request,
    run_id: str,
) -> dict[str, object] | None:
    """Return one background explore search run snapshot."""

    database_url = request.app.state.database_url
    user = get_current_user(request, database_url=database_url)
    return get_explore_search_run(
        run_id,
        viewer_user_id=user.user_id if user else None,
        guest_access_token=request.headers.get("X-Search-Run-Token"),
        database_url=database_url,
    )


def expand_explore_search_run_response(
    request: Request,
    run_id: str,
    payload: dict[str, object],
) -> dict[str, object] | None:
    """Start one pending query for an existing Explore search run."""

    database_url = request.app.state.database_url
    user = get_current_user(request, database_url=database_url)
    try:
        return expand_explore_search_run(
            run_id,
            authorize_attempt=lambda topic: _authorize_explore_search_request(
                request, {"topicDescription": topic, "turnstileToken": payload.get("turnstileToken")},
            ),
            viewer_user_id=user.user_id if user else None,
            guest_access_token=request.headers.get("X-Search-Run-Token"),
            database_url=database_url,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


def _authorize_explore_search_request(
    request: Request,
    payload: dict[str, object],
) -> tuple[str, str]:
    database_url = request.app.state.database_url
    topic_description = str(payload.get("topicDescription") or "").strip()
    turnstile_token = str(payload.get("turnstileToken") or "").strip()
    topic_hash = hash_explore_topic(topic_description)
    user = get_current_user(request, database_url=database_url)
    actor = resolve_explore_actor(
        request,
        user,
        database_url=database_url,
    )
    turnstile_verified = False
    quota_bypassed = has_search_quota_bypass(user.email if user else None)

    if actor.tier is ExploreTier.SUSPICIOUS and turnstile_token:
        verification = verify_turnstile_token(
            turnstile_token,
            remote_ip=read_explore_client_ip(request),
        )
        if not verification.success:
            decision = build_turnstile_failure_decision(
                service_unavailable=verification.service_unavailable
            )
            record_blocked_explore_attempt(
                actor,
                decision,
                topic_hash=topic_hash,
                database_url=database_url,
            )
            raise build_explore_access_denied_error(decision)
        turnstile_verified = True

    decision = reserve_explore_access(
        actor,
        topic_hash=topic_hash,
        turnstile_verified=turnstile_verified,
        bypass_quota=quota_bypassed,
        database_url=database_url,
    )

    if not decision.allowed:
        raise build_explore_access_denied_error(decision)

    return topic_description, topic_hash

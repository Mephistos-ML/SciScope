"""Explore search route."""

from __future__ import annotations

from fastapi import Request
from fastapi import HTTPException, status

from app.models import ExploreTier
from app.services.auth import get_current_user
from app.services.features import has_feature
from app.services.security import verify_turnstile_token
from app.services.search.access import (
    build_explore_access_denied_error,
    build_turnstile_failure_decision,
    check_explore_access,
    hash_explore_topic,
    has_search_quota_bypass,
    read_explore_client_ip,
    record_allowed_explore_attempt,
    record_blocked_explore_attempt,
    resolve_explore_actor,
)
from app.services.search.explore import (
    create_explore_search_job,
    get_explore_search_job,
    run_explore_search,
)
from app.services.search.explore.response import ExploreResponseMode
from app.services.search.observability import SearchLogContext, build_request_id


def search_explore_response(
    request: Request,
    payload: dict[str, object],
) -> dict[str, object]:
    """Run an explore search from one topic description."""

    topic_description, topic_hash, response_mode = _authorize_explore_search_request(
        request,
        payload,
    )
    return run_explore_search(
        topic_description=topic_description,
        response_mode=response_mode,
        database_url=request.app.state.database_url,
        log_context=SearchLogContext(
            request_id=build_request_id(),
            topic_hash=topic_hash,
        ),
    )


def create_explore_search_job_response(
    request: Request,
    payload: dict[str, object],
) -> dict[str, object]:
    """Create one background explore search job."""

    topic_description, topic_hash, response_mode = _authorize_explore_search_request(
        request,
        payload,
    )
    return create_explore_search_job(
        topic_description=topic_description,
        response_mode=response_mode,
        log_context=SearchLogContext(
            request_id=build_request_id(),
            topic_hash=topic_hash,
        ),
    )


def get_explore_search_job_response(
    request: Request,
    job_id: str,
) -> dict[str, object] | None:
    """Return one background explore search job snapshot."""

    payload = get_explore_search_job(job_id)
    if payload is None:
        return None
    if payload.get("responseMode") == "beta":
        user = get_current_user(
            request,
            database_url=request.app.state.database_url,
        )
        if not has_feature(user.email if user else None, "explore_beta"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Beta access is not enabled for this account.",
            )
    return payload


def _authorize_explore_search_request(
    request: Request,
    payload: dict[str, object],
) -> tuple[str, str, ExploreResponseMode]:
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

    decision = check_explore_access(
        actor,
        turnstile_verified=turnstile_verified,
        bypass_quota=quota_bypassed,
        database_url=database_url,
    )

    if not decision.allowed:
        record_blocked_explore_attempt(
            actor,
            decision,
            topic_hash=topic_hash,
            database_url=database_url,
        )
        raise build_explore_access_denied_error(decision)

    beta_requested = bool(payload.get("betaMode"))
    if beta_requested and not has_feature(user.email if user else None, "explore_beta"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beta access is not enabled for this account.",
        )

    record_allowed_explore_attempt(
        actor,
        topic_hash=topic_hash,
        quota_bypassed=quota_bypassed,
        database_url=database_url,
    )
    response_mode = "beta" if beta_requested else "canonical"
    return topic_description, topic_hash, response_mode

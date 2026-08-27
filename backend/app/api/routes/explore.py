"""Explore search route."""

from __future__ import annotations

from fastapi import Request

from app.models import ExploreTier
from app.services.auth import get_current_user
from app.services.security import verify_turnstile_token
from app.services.search.access import (
    build_explore_access_denied_error,
    build_turnstile_failure_decision,
    check_explore_access,
    hash_explore_topic,
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
from app.services.search.observability import SearchLogContext, build_request_id


def search_explore_response(
    request: Request,
    payload: dict[str, object],
) -> dict[str, object]:
    """Run an explore search from one topic description."""

    topic_description, topic_hash = _authorize_explore_search_request(request, payload)
    return run_explore_search(
        topic_description=topic_description,
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

    topic_description, topic_hash = _authorize_explore_search_request(request, payload)
    return create_explore_search_job(
        topic_description=topic_description,
        log_context=SearchLogContext(
            request_id=build_request_id(),
            topic_hash=topic_hash,
        ),
    )


def get_explore_search_job_response(job_id: str) -> dict[str, object] | None:
    """Return one background explore search job snapshot."""

    return get_explore_search_job(job_id)


def _authorize_explore_search_request(
    request: Request,
    payload: dict[str, object],
) -> tuple[str, str]:
    database_url = request.app.state.database_url
    topic_description = str(payload.get("topicDescription") or "").strip()
    turnstile_token = str(payload.get("turnstileToken") or "").strip()
    topic_hash = hash_explore_topic(topic_description)
    actor = resolve_explore_actor(
        request,
        get_current_user(request, database_url=database_url),
        database_url=database_url,
    )
    turnstile_verified = False

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

    record_allowed_explore_attempt(
        actor,
        topic_hash=topic_hash,
        database_url=database_url,
    )
    return topic_description, topic_hash

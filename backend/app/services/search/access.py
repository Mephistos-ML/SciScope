"""Access orchestration for explore abuse protection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib

from fastapi import Request

from app.config import (
    EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD,
    EXPLORE_SUSPICIOUS_WINDOW_SECONDS,
    TURNSTILE_ENABLED,
)
from app.models.explore_access import (
    ExploreAccessDecision,
    ExploreAccessOutcome,
    ExploreActor,
    ExploreLimitCode,
    ExploreTier,
)
from app.services.auth import User
from app.services.search.policy import (
    build_cooldown_decision,
    build_global_capacity_decision,
    build_public_access_disabled_decision,
    build_quota_decision,
    build_turnstile_required_decision,
    build_turnstile_verification_failed_decision,
    get_explore_policy_for_actor,
    get_global_explore_daily_limit,
    should_require_turnstile,
)
from app.storage.explore import (
    count_explore_events_since,
    count_global_explore_events_since,
    get_first_explore_event_at_since,
    get_last_explore_event_at,
    record_explore_search_event,
)

SUSPICIOUS_GUEST_OUTCOMES = (
    str(ExploreAccessOutcome.BLOCKED_COOLDOWN),
    str(ExploreAccessOutcome.BLOCKED_QUOTA),
    str(ExploreAccessOutcome.BLOCKED_TURNSTILE),
)


def resolve_explore_actor(
    request: Request,
    user: User | None,
    *,
    now: datetime | None = None,
    database_url: str | None = None,
) -> ExploreActor:
    """Resolve the current explore actor from request and optional user."""

    if user is not None:
        return ExploreActor(
            tier=ExploreTier.USER,
            subject_type="user",
            subject_key=user.user_id,
            user_id=user.user_id,
        )

    raw_ip = read_explore_client_ip(request)
    ip_hash = _hash_value(raw_ip or "unknown")
    tier = _resolve_guest_tier(
        ip_hash,
        now=now,
        database_url=database_url,
    )
    return ExploreActor(
        tier=tier,
        subject_type="guest_ip",
        subject_key=ip_hash,
        ip_hash=ip_hash,
    )


def check_explore_access(
    actor: ExploreActor,
    *,
    turnstile_verified: bool = False,
    now: datetime | None = None,
    database_url: str | None = None,
) -> ExploreAccessDecision:
    """Return whether the actor may run a new explore search."""

    current_time = _ensure_utc(now or _utc_now())
    policy = get_explore_policy_for_actor(actor)

    if not policy.public_access_enabled:
        return build_public_access_disabled_decision()

    if should_require_turnstile(actor) and not turnstile_verified:
        return build_turnstile_required_decision()

    quota_window_start = current_time - timedelta(seconds=policy.quota_window_seconds)
    global_limit = get_global_explore_daily_limit()
    global_count = count_global_explore_events_since(
        since=quota_window_start,
        outcomes=(str(ExploreAccessOutcome.ALLOWED),),
        database_url=database_url,
    )
    if global_count >= global_limit:
        return build_global_capacity_decision()

    last_allowed_event_at = get_last_explore_event_at(
        subject_type=actor.subject_type,
        subject_key=actor.subject_key,
        outcomes=(str(ExploreAccessOutcome.ALLOWED),),
        database_url=database_url,
    )
    if last_allowed_event_at is not None:
        next_allowed_at = last_allowed_event_at + timedelta(
            seconds=policy.cooldown_seconds
        )
        if next_allowed_at > current_time:
            retry_after_seconds = int((next_allowed_at - current_time).total_seconds())
            return build_cooldown_decision(
                actor,
                retry_after_seconds=max(retry_after_seconds, 1),
            )

    actor_count = count_explore_events_since(
        subject_type=actor.subject_type,
        subject_key=actor.subject_key,
        since=quota_window_start,
        outcomes=(str(ExploreAccessOutcome.ALLOWED),),
        database_url=database_url,
    )
    if actor_count >= policy.daily_limit:
        first_allowed_event_at = get_first_explore_event_at_since(
            subject_type=actor.subject_type,
            subject_key=actor.subject_key,
            since=quota_window_start,
            outcomes=(str(ExploreAccessOutcome.ALLOWED),),
            database_url=database_url,
        )
        next_reset_at = (first_allowed_event_at or current_time) + timedelta(
            seconds=policy.quota_window_seconds
        )
        retry_after_seconds = int((next_reset_at - current_time).total_seconds())
        return build_quota_decision(
            actor,
            retry_after_seconds=max(retry_after_seconds, 1),
        )

    return ExploreAccessDecision(allowed=True)


def record_allowed_explore_attempt(
    actor: ExploreActor,
    *,
    topic_hash: str,
    created_at: datetime | None = None,
    database_url: str | None = None,
) -> None:
    """Persist one allowed explore attempt."""

    record_explore_search_event(
        user_id=actor.user_id,
        subject_type=actor.subject_type,
        subject_key=actor.subject_key,
        ip_hash=actor.ip_hash,
        topic_hash=topic_hash,
        outcome=str(ExploreAccessOutcome.ALLOWED),
        created_at=created_at,
        database_url=database_url,
    )


def record_blocked_explore_attempt(
    actor: ExploreActor,
    decision: ExploreAccessDecision,
    *,
    topic_hash: str,
    created_at: datetime | None = None,
    database_url: str | None = None,
) -> None:
    """Persist one blocked explore attempt."""

    record_explore_search_event(
        user_id=actor.user_id,
        subject_type=actor.subject_type,
        subject_key=actor.subject_key,
        ip_hash=actor.ip_hash,
        topic_hash=topic_hash,
        outcome=_map_blocked_decision_to_outcome(decision),
        retry_after_seconds=decision.retry_after_seconds,
        created_at=created_at,
        database_url=database_url,
    )


def hash_explore_topic(topic_description: str) -> str:
    """Return a normalized topic hash for one explore request."""

    normalized = " ".join(topic_description.strip().lower().split())
    return _hash_value(normalized or "empty")


def build_turnstile_failure_decision(
    *,
    service_unavailable: bool = False,
) -> ExploreAccessDecision:
    """Return one denial decision for an invalid or unavailable Turnstile check."""

    return build_turnstile_verification_failed_decision(
        service_unavailable=service_unavailable
    )


def read_explore_client_ip(request: Request) -> str | None:
    """Return the best-effort client IP address for one explore request."""

    return _read_client_ip(request)


def _map_blocked_decision_to_outcome(decision: ExploreAccessDecision) -> str:
    if decision.turnstile_required:
        return str(ExploreAccessOutcome.BLOCKED_TURNSTILE)
    if decision.code is ExploreLimitCode.GLOBAL_CAPACITY_REACHED:
        return str(ExploreAccessOutcome.BLOCKED_CAPACITY)
    if decision.code in {
        ExploreLimitCode.GUEST_COOLDOWN,
        ExploreLimitCode.USER_COOLDOWN,
    }:
        return str(ExploreAccessOutcome.BLOCKED_COOLDOWN)
    if decision.code is ExploreLimitCode.GUEST_SEARCH_DISABLED:
        return str(ExploreAccessOutcome.BLOCKED_DISABLED)
    return str(ExploreAccessOutcome.BLOCKED_QUOTA)


def _resolve_guest_tier(
    subject_key: str,
    *,
    now: datetime | None = None,
    database_url: str | None = None,
) -> ExploreTier:
    if not TURNSTILE_ENABLED:
        return ExploreTier.GUEST

    current_time = _ensure_utc(now or _utc_now())
    suspicious_window_start = current_time - timedelta(
        seconds=EXPLORE_SUSPICIOUS_WINDOW_SECONDS
    )
    blocked_count = count_explore_events_since(
        subject_type="guest_ip",
        subject_key=subject_key,
        since=suspicious_window_start,
        outcomes=SUSPICIOUS_GUEST_OUTCOMES,
        database_url=database_url,
    )
    if blocked_count >= EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD:
        return ExploreTier.SUSPICIOUS
    return ExploreTier.GUEST


def _read_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    client = request.client
    if client is not None and client.host:
        return client.host.strip()
    return None


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

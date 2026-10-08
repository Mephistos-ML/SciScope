"""Access orchestration for explore abuse protection."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import hashlib

from app.config import (
    EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD,
    EXPLORE_SUSPICIOUS_WINDOW_SECONDS,
    TURNSTILE_ENABLED,
)
from app.models.explore_access import (
    ExploreAdmission,
    ExploreAccessDecision,
    ExploreAccessOutcome,
    ExploreActor,
    ExploreLimitCode,
    ExploreTier,
    ExploreUsage,
)
from app.models.auth import User
from app.models.security import TurnstileVerificationResult
from app.services.search.access.errors import ExploreAccessDeniedError
from app.services.search.access.policy import (
    has_search_quota_bypass,
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
    record_explore_search_event,
)

from app.storage.search_admission import ExploreAdmissionStore, explore_admission_transaction

SUSPICIOUS_GUEST_OUTCOMES = (
    str(ExploreAccessOutcome.BLOCKED_COOLDOWN),
    str(ExploreAccessOutcome.BLOCKED_QUOTA),
    str(ExploreAccessOutcome.BLOCKED_TURNSTILE),
)


def resolve_explore_actor(
    user: User | None,
    *,
    client_ip: str | None,
    now: datetime | None = None,
    database_url: str,
) -> ExploreActor:
    """Resolve the Explore actor from an authenticated user and explicit client address."""

    if user is not None:
        return ExploreActor(
            tier=ExploreTier.USER,
            subject_type="user",
            subject_key=user.user_id,
            user_id=user.user_id,
        )

    ip_hash = _hash_value(client_ip or "unknown")
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
    bypass_quota: bool = False,
    usage: ExploreUsage,
    now: datetime | None = None,
) -> ExploreAccessDecision:
    """Return whether the actor may run a new explore search."""

    current_time = _ensure_utc(now or _utc_now())
    policy = get_explore_policy_for_actor(actor)

    if not policy.public_access_enabled:
        return build_public_access_disabled_decision()

    if should_require_turnstile(actor) and not turnstile_verified:
        return build_turnstile_required_decision()

    if bypass_quota:
        return ExploreAccessDecision(allowed=True)

    global_limit = get_global_explore_daily_limit()
    global_count = usage.global_count
    if global_count >= global_limit:
        return build_global_capacity_decision()

    last_allowed_event_at = usage.last_allowed_at
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

    actor_count = usage.actor_count
    if actor_count >= policy.daily_limit:
        first_allowed_event_at = usage.first_allowed_at
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
    quota_bypassed: bool = False,
    created_at: datetime | None = None,
    database_url: str,
) -> None:
    """Persist one allowed explore attempt."""

    record_explore_search_event(
        user_id=actor.user_id,
        subject_type=actor.subject_type,
        subject_key=actor.subject_key,
        ip_hash=actor.ip_hash,
        topic_hash=topic_hash,
        outcome=str(
            ExploreAccessOutcome.ALLOWED_INTERNAL
            if quota_bypassed
            else ExploreAccessOutcome.ALLOWED
        ),
        created_at=created_at,
        database_url=database_url,
    )


def record_blocked_explore_attempt(
    actor: ExploreActor,
    decision: ExploreAccessDecision,
    *,
    topic_hash: str,
    created_at: datetime | None = None,
    database_url: str,
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


def _resolve_guest_tier(
    ip_hash: str,
    *,
    now: datetime | None = None,
    database_url: str,
) -> ExploreTier:
    if not TURNSTILE_ENABLED:
        return ExploreTier.GUEST

    current_time = _ensure_utc(now or _utc_now())
    suspicious_window_start = current_time - timedelta(
        seconds=EXPLORE_SUSPICIOUS_WINDOW_SECONDS
    )
    blocked_count = count_explore_events_since(
        subject_type="guest_ip",
        subject_key=ip_hash,
        since=suspicious_window_start,
        outcomes=SUSPICIOUS_GUEST_OUTCOMES,
        database_url=database_url,
    )
    if blocked_count >= EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD:
        return ExploreTier.SUSPICIOUS
    return ExploreTier.GUEST


def _map_blocked_decision_to_outcome(decision: ExploreAccessDecision) -> str:
    if decision.code in {
        ExploreLimitCode.GUEST_COOLDOWN,
        ExploreLimitCode.USER_COOLDOWN,
    }:
        return str(ExploreAccessOutcome.BLOCKED_COOLDOWN)
    if decision.code in {
        ExploreLimitCode.GUEST_QUOTA_EXCEEDED,
        ExploreLimitCode.USER_QUOTA_EXCEEDED,
        ExploreLimitCode.GUEST_SEARCH_DISABLED,
    }:
        return str(ExploreAccessOutcome.BLOCKED_QUOTA)
    if decision.code in {
        ExploreLimitCode.TURNSTILE_REQUIRED,
        ExploreLimitCode.TURNSTILE_VERIFICATION_FAILED,
    }:
        return str(ExploreAccessOutcome.BLOCKED_TURNSTILE)
    return str(ExploreAccessOutcome.BLOCKED_CAPACITY)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def reserve_explore_access(
    actor: ExploreActor, *, topic_hash: str, turnstile_verified: bool = False,
    bypass_quota: bool = False, now: datetime | None = None, database_url: str,
) -> ExploreAccessDecision:
    """Decide and persist admission before another request can consume capacity."""
    with explore_admission_transaction(database_url=database_url) as store:
        return record_explore_admission(
            actor, store=store, topic_hash=topic_hash, turnstile_verified=turnstile_verified,
            bypass_quota=bypass_quota, now=now,
        )


def record_explore_admission(
    actor: ExploreActor, *, store: ExploreAdmissionStore, topic_hash: str,
    turnstile_verified: bool = False, bypass_quota: bool = False,
    now: datetime | None = None,
) -> ExploreAccessDecision:
    """Apply admission policy and record its outcome in the caller's transaction."""
    current_time = _ensure_utc(now or _utc_now())
    policy = get_explore_policy_for_actor(actor)
    usage = store.read_usage(subject_type=actor.subject_type, subject_key=actor.subject_key,
                             since=current_time - timedelta(seconds=policy.quota_window_seconds))
    decision = check_explore_access(actor, turnstile_verified=turnstile_verified,
                                    bypass_quota=bypass_quota, now=current_time,
                                    usage=usage)
    outcome = (str(ExploreAccessOutcome.ALLOWED_INTERNAL if bypass_quota else ExploreAccessOutcome.ALLOWED)
               if decision.allowed else _map_blocked_decision_to_outcome(decision))
    store.record_event(user_id=actor.user_id, subject_type=actor.subject_type,
                       subject_key=actor.subject_key, ip_hash=actor.ip_hash,
                       topic_hash=topic_hash, outcome=outcome, created_at=current_time,
                       retry_after_seconds=decision.retry_after_seconds)
    return decision


def prepare_explore_admission(
    *, user: User | None, client_ip: str | None, topic_description: str,
    turnstile_token: str, verify_turnstile_token: Callable[..., TurnstileVerificationResult],
    database_url: str,
) -> ExploreAdmission:
    """Apply abuse-proof policy and audit denials before the admission transaction."""
    topic_hash = hash_explore_topic(topic_description)
    actor = resolve_explore_actor(
        user,
        client_ip=client_ip,
        database_url=database_url,
    )
    turnstile_verified = False
    quota_bypassed = has_search_quota_bypass(user.email if user else None)

    if actor.tier is ExploreTier.SUSPICIOUS and turnstile_token:
        verification = verify_turnstile_token(
            turnstile_token,
            remote_ip=client_ip,
        )
        if not verification.success:
            decision = build_turnstile_verification_failed_decision(
                service_unavailable=verification.service_unavailable
            )
            record_blocked_explore_attempt(
                actor,
                decision,
                topic_hash=topic_hash,
                database_url=database_url,
            )
            raise ExploreAccessDeniedError(decision)
        turnstile_verified = True

    return ExploreAdmission(
        actor=actor, turnstile_verified=turnstile_verified, bypass_quota=quota_bypassed,
    )

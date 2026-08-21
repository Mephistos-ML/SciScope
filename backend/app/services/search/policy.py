"""Policy rules for explore access control."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import (
    EXPLORE_GLOBAL_DAILY_LIMIT,
    EXPLORE_GUEST_COOLDOWN_SECONDS,
    EXPLORE_GUEST_DAILY_LIMIT,
    EXPLORE_PUBLIC_GUEST_SEARCH_ENABLED,
    EXPLORE_QUOTA_WINDOW_SECONDS,
    EXPLORE_USER_COOLDOWN_SECONDS,
    EXPLORE_USER_DAILY_LIMIT,
    TURNSTILE_ENABLED,
)
from app.models.explore_access import (
    ExploreAccessDecision,
    ExploreActor,
    ExploreLimitCode,
    ExploreTier,
)


@dataclass(frozen=True)
class ExploreAccessPolicy:
    """Resolved policy for one explore actor."""

    tier: ExploreTier
    public_access_enabled: bool
    quota_window_seconds: int
    daily_limit: int
    cooldown_seconds: int
    sign_in_suggested: bool


def get_explore_policy_for_actor(actor: ExploreActor) -> ExploreAccessPolicy:
    """Return the active explore policy for one actor."""

    if actor.tier is ExploreTier.GUEST:
        return ExploreAccessPolicy(
            tier=actor.tier,
            public_access_enabled=EXPLORE_PUBLIC_GUEST_SEARCH_ENABLED,
            quota_window_seconds=EXPLORE_QUOTA_WINDOW_SECONDS,
            daily_limit=EXPLORE_GUEST_DAILY_LIMIT,
            cooldown_seconds=EXPLORE_GUEST_COOLDOWN_SECONDS,
            sign_in_suggested=True,
        )

    if actor.tier is ExploreTier.SUSPICIOUS:
        return ExploreAccessPolicy(
            tier=actor.tier,
            public_access_enabled=TURNSTILE_ENABLED,
            quota_window_seconds=EXPLORE_QUOTA_WINDOW_SECONDS,
            daily_limit=1,
            cooldown_seconds=max(EXPLORE_GUEST_COOLDOWN_SECONDS, 60),
            sign_in_suggested=True,
        )

    return ExploreAccessPolicy(
        tier=actor.tier,
        public_access_enabled=True,
        quota_window_seconds=EXPLORE_QUOTA_WINDOW_SECONDS,
        daily_limit=EXPLORE_USER_DAILY_LIMIT,
        cooldown_seconds=EXPLORE_USER_COOLDOWN_SECONDS,
        sign_in_suggested=False,
    )


def get_global_explore_daily_limit() -> int:
    """Return the global explore usage cap for the active window."""

    return EXPLORE_GLOBAL_DAILY_LIMIT


def should_require_turnstile(actor: ExploreActor) -> bool:
    """Return whether the actor must complete a Turnstile challenge."""

    return TURNSTILE_ENABLED and actor.tier is ExploreTier.SUSPICIOUS


def build_public_access_disabled_decision() -> ExploreAccessDecision:
    """Return the guest denial state when public explore is disabled."""

    return ExploreAccessDecision(
        allowed=False,
        code=ExploreLimitCode.GUEST_SEARCH_DISABLED,
        message="Public explore is unavailable right now. Sign in to continue.",
        sign_in_suggested=True,
    )


def build_cooldown_decision(
    actor: ExploreActor,
    *,
    retry_after_seconds: int,
) -> ExploreAccessDecision:
    """Return one cooldown denial decision."""

    retry_message = _format_retry_after(retry_after_seconds)
    if actor.tier is ExploreTier.GUEST:
        return ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.GUEST_COOLDOWN,
            message=f"Please wait {retry_message} before running another search.",
            retry_after_seconds=retry_after_seconds,
            sign_in_suggested=True,
        )

    return ExploreAccessDecision(
        allowed=False,
        code=ExploreLimitCode.USER_COOLDOWN,
        message=f"Please wait {retry_message} before running another search.",
        retry_after_seconds=retry_after_seconds,
    )


def build_quota_decision(
    actor: ExploreActor,
    *,
    retry_after_seconds: int,
) -> ExploreAccessDecision:
    """Return one daily quota denial decision."""

    retry_message = _format_retry_after(retry_after_seconds)
    if actor.tier is ExploreTier.GUEST:
        return ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.GUEST_QUOTA_EXCEEDED,
            message=(
                "You’ve reached the public explore limit. "
                f"Try again in {retry_message}, or sign in to continue."
            ),
            retry_after_seconds=retry_after_seconds,
            sign_in_suggested=True,
        )

    return ExploreAccessDecision(
        allowed=False,
        code=ExploreLimitCode.USER_QUOTA_EXCEEDED,
        message=f"You’ve reached today’s search limit. Try again in {retry_message}.",
        retry_after_seconds=retry_after_seconds,
    )


def build_global_capacity_decision(
    *,
    retry_after_seconds: int | None = None,
) -> ExploreAccessDecision:
    """Return one global capacity denial decision."""

    return ExploreAccessDecision(
        allowed=False,
        code=ExploreLimitCode.GLOBAL_CAPACITY_REACHED,
        message="Explore is temporarily limited due to system capacity. Please try again later.",
        retry_after_seconds=retry_after_seconds,
    )


def build_turnstile_required_decision() -> ExploreAccessDecision:
    """Return one Turnstile challenge requirement decision."""

    return ExploreAccessDecision(
        allowed=False,
        code=ExploreLimitCode.TURNSTILE_REQUIRED,
        message="Please complete the verification challenge before continuing.",
        turnstile_required=True,
    )


def _format_retry_after(retry_after_seconds: int) -> str:
    if retry_after_seconds <= 59:
        unit = "second" if retry_after_seconds == 1 else "seconds"
        return f"{retry_after_seconds} {unit}"

    total_minutes, seconds = divmod(retry_after_seconds, 60)
    if total_minutes < 60:
        if seconds == 0:
            unit = "minute" if total_minutes == 1 else "minutes"
            return f"{total_minutes} {unit}"
        minute_unit = "minute" if total_minutes == 1 else "minutes"
        second_unit = "second" if seconds == 1 else "seconds"
        return f"{total_minutes} {minute_unit} {seconds} {second_unit}"

    hours, minutes = divmod(total_minutes, 60)
    hour_unit = "hour" if hours == 1 else "hours"
    minute_unit = "minute" if minutes == 1 else "minutes"
    return f"{hours} {hour_unit} {minutes} {minute_unit}"

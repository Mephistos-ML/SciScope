"""Structured errors for explore access control."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.explore_access import ExploreAccessDecision, ExploreLimitCode


@dataclass(frozen=True)
class ExploreAccessDeniedError(RuntimeError):
    """Base error for denied explore access attempts."""

    code: ExploreLimitCode
    message: str
    retry_after_seconds: int | None = None
    sign_in_suggested: bool = False
    turnstile_required: bool = False
    status_code: int = 429

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    def to_payload(self) -> dict[str, object]:
        """Return a stable JSON-friendly API payload."""

        payload: dict[str, object] = {
            "error": self.message,
            "code": str(self.code),
            "signInSuggested": self.sign_in_suggested,
            "turnstileRequired": self.turnstile_required,
        }
        if self.retry_after_seconds is not None:
            payload["retryAfterSeconds"] = self.retry_after_seconds
        return payload


class ExploreCooldownError(ExploreAccessDeniedError):
    """Raised when an explore actor must wait before the next search."""


class ExploreQuotaExceededError(ExploreAccessDeniedError):
    """Raised when an explore actor exceeds the active search window quota."""


class ExploreTurnstileRequiredError(ExploreAccessDeniedError):
    """Raised when an explore actor must complete a Turnstile challenge."""


class ExploreCapacityError(ExploreAccessDeniedError):
    """Raised when global explore capacity protection blocks new searches."""

    def __init__(
        self,
        *,
        code: ExploreLimitCode,
        message: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            retry_after_seconds=retry_after_seconds,
            status_code=503,
        )


def build_explore_access_denied_error(
    decision: ExploreAccessDecision,
) -> ExploreAccessDeniedError:
    """Convert one denied access decision into the API error contract."""

    if decision.allowed:
        raise ValueError("Allowed explore decisions cannot be converted to errors.")

    if decision.message is None or decision.code is None:
        raise ValueError("Denied explore decisions must include code and message.")

    if decision.turnstile_required:
        return ExploreTurnstileRequiredError(
            code=decision.code,
            message=decision.message,
            retry_after_seconds=decision.retry_after_seconds,
            sign_in_suggested=decision.sign_in_suggested,
            turnstile_required=True,
            status_code=403,
        )

    if decision.code is ExploreLimitCode.GLOBAL_CAPACITY_REACHED:
        return ExploreCapacityError(
            code=decision.code,
            message=decision.message,
            retry_after_seconds=decision.retry_after_seconds,
        )

    if decision.code in {
        ExploreLimitCode.GUEST_COOLDOWN,
        ExploreLimitCode.USER_COOLDOWN,
    }:
        return ExploreCooldownError(
            code=decision.code,
            message=decision.message,
            retry_after_seconds=decision.retry_after_seconds,
            sign_in_suggested=decision.sign_in_suggested,
        )

    if decision.code is ExploreLimitCode.GUEST_SEARCH_DISABLED:
        return ExploreAccessDeniedError(
            code=decision.code,
            message=decision.message,
            retry_after_seconds=decision.retry_after_seconds,
            sign_in_suggested=decision.sign_in_suggested,
            status_code=403,
        )

    return ExploreQuotaExceededError(
        code=decision.code,
        message=decision.message,
        retry_after_seconds=decision.retry_after_seconds,
        sign_in_suggested=decision.sign_in_suggested,
    )

"""Structured errors for explore access control."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.explore_access import ExploreLimitCode


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


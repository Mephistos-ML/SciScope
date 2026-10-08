"""Policy for accepting and verifying anti-abuse proof."""

from collections.abc import Callable

from app.models.security import TurnstileVerificationResult

TURNSTILE_MAX_TOKEN_LENGTH = 2048


def verify_turnstile_token(
    token: str, *, enabled: bool, verify: Callable[..., TurnstileVerificationResult],
    remote_ip: str | None = None,
) -> TurnstileVerificationResult:
    """Apply enablement and input limits before invoking the verification capability."""
    normalized_token = token.strip()
    if not enabled:
        return TurnstileVerificationResult(success=True)
    if not normalized_token:
        return TurnstileVerificationResult(
            success=False,
            error_codes=("missing-input-response",),
        )
    if len(normalized_token) > TURNSTILE_MAX_TOKEN_LENGTH:
        return TurnstileVerificationResult(
            success=False,
            error_codes=("invalid-input-response",),
        )

    return verify(normalized_token, remote_ip=remote_ip)

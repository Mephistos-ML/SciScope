"""Security verification outcomes shared with external adapters."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnstileVerificationResult:
    """Result of one server-side Turnstile verification request."""

    success: bool
    error_codes: tuple[str, ...] = ()
    service_unavailable: bool = False

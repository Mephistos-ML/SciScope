"""Cloudflare Turnstile verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from app.config import (
    TURNSTILE_ENABLED,
    TURNSTILE_SECRET_KEY,
    TURNSTILE_VERIFY_TIMEOUT_SECONDS,
)

TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_MAX_TOKEN_LENGTH = 2048


@dataclass(frozen=True)
class TurnstileVerificationResult:
    """Result of one server-side Turnstile verification request."""

    success: bool
    error_codes: tuple[str, ...] = ()
    service_unavailable: bool = False


def verify_turnstile_token(
    token: str,
    *,
    remote_ip: str | None = None,
) -> TurnstileVerificationResult:
    """Validate one Turnstile token against Cloudflare Siteverify."""

    normalized_token = token.strip()
    if not TURNSTILE_ENABLED:
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

    form_payload = {
        "secret": TURNSTILE_SECRET_KEY,
        "response": normalized_token,
        "idempotency_key": str(uuid4()),
    }
    if remote_ip:
        form_payload["remoteip"] = remote_ip

    request = Request(
        TURNSTILE_SITEVERIFY_URL,
        data=urlencode(form_payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=TURNSTILE_VERIFY_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, URLError, json.JSONDecodeError):
        return TurnstileVerificationResult(
            success=False,
            error_codes=("internal-error",),
            service_unavailable=True,
        )

    error_codes = tuple(
        str(code).strip()
        for code in payload.get("error-codes", [])
        if str(code).strip()
    )
    return TurnstileVerificationResult(
        success=bool(payload.get("success")),
        error_codes=error_codes,
    )

"""Cloudflare Siteverify protocol and response mapping."""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from app.models.security import TurnstileVerificationResult

TURNSTILE_MAX_RESPONSE_BYTES = 65536
TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(
    token: str, *, secret_key: str, timeout_seconds: float, remote_ip: str | None = None,
) -> TurnstileVerificationResult:
    """Send one bounded verification request; report provider outages as unavailable."""
    form_payload = {
        "secret": secret_key,
        "response": token,
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
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(TURNSTILE_MAX_RESPONSE_BYTES + 1)
        if len(raw) > TURNSTILE_MAX_RESPONSE_BYTES:
            raise ValueError("Turnstile response exceeded its size limit.")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or type(payload.get("success")) is not bool:
            raise ValueError("Turnstile response must contain a boolean success field.")
        codes = payload.get("error-codes", [])
        if not isinstance(codes, list) or any(not isinstance(code, str) for code in codes):
            raise ValueError("Turnstile error codes must be a list of strings.")
    except (OSError, ValueError):
        return TurnstileVerificationResult(
            success=False,
            error_codes=("internal-error",),
            service_unavailable=True,
        )

    return TurnstileVerificationResult(
        success=payload["success"],
        error_codes=tuple(code.strip() for code in codes if code.strip()),
    )

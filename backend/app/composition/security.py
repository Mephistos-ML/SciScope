"""Bind anti-abuse verification policy to the configured Cloudflare adapter."""

from collections.abc import Callable
from functools import partial

from app import config
from app.models.security import TurnstileVerificationResult
from app.integrations.security.cloudflare.turnstile import verify_turnstile_token as verify_cloudflare_token
from app.services.security.turnstile import verify_turnstile_token


def build_turnstile_verifier() -> Callable[..., TurnstileVerificationResult]:
    """Supply one process's verification dependency without making network requests."""
    return partial(
        verify_turnstile_token, enabled=config.TURNSTILE_ENABLED,
        verify=partial(
            verify_cloudflare_token, secret_key=config.TURNSTILE_SECRET_KEY,
            timeout_seconds=config.TURNSTILE_VERIFY_TIMEOUT_SECONDS,
        ),
    )

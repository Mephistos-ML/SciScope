"""Authentication helpers for GitHub API requests."""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import jwt

from app.config import (
    APP_VERSION,
    GITHUB_APP_ID,
    GITHUB_APP_INSTALLATION_ID,
    GITHUB_APP_PRIVATE_KEY,
    GITHUB_AUTH_MODE,
)
from app.sources.repositories.common import RepositorySourceError


GITHUB_API_BASE = "https://api.github.com"
GITHUB_AUTH_TIMEOUT_SECONDS = 30
GITHUB_TOKEN_REFRESH_BUFFER_SECONDS = 60

_INSTALLATION_TOKEN_CACHE: dict[str, object] = {
    "token": "",
    "expires_at": None,
}
_INSTALLATION_TOKEN_LOCK = threading.Lock()


def build_user_agent() -> str:
    """Build the application user agent for outbound GitHub requests."""

    return f"SciScope/{APP_VERSION}"


def build_auth_headers() -> dict[str, str]:
    """Build required authentication headers for GitHub API requests."""

    if GITHUB_AUTH_MODE == "disabled":
        raise RepositorySourceError(
            source="github",
            status="disabled",
            public_message="GitHub repository search is disabled in this environment.",
        )

    if GITHUB_AUTH_MODE != "app":
        raise RepositorySourceError(
            source="github",
            status="misconfigured",
            public_message=(
                "GitHub repository search is misconfigured. Expected "
                "GITHUB_AUTH_MODE=app or disabled."
            ),
        )

    missing_settings = [
        name
        for name, value in (
            ("GITHUB_APP_ID", GITHUB_APP_ID),
            ("GITHUB_APP_INSTALLATION_ID", GITHUB_APP_INSTALLATION_ID),
            ("GITHUB_APP_PRIVATE_KEY", GITHUB_APP_PRIVATE_KEY),
        )
        if not value
    ]
    if missing_settings:
        raise RepositorySourceError(
            source="github",
            status="misconfigured",
            public_message=(
                "GitHub repository search is misconfigured. Missing settings: "
                + ", ".join(missing_settings)
                + "."
            ),
        )

    token = _get_installation_access_token()
    return {"Authorization": f"Bearer {token}"}


def _get_installation_access_token() -> str:
    cached_token = str(_INSTALLATION_TOKEN_CACHE.get("token") or "")
    cached_expires_at = _INSTALLATION_TOKEN_CACHE.get("expires_at")
    if (
        cached_token
        and isinstance(cached_expires_at, datetime)
        and cached_expires_at
        > datetime.now(UTC) + timedelta(seconds=GITHUB_TOKEN_REFRESH_BUFFER_SECONDS)
    ):
        return cached_token

    with _INSTALLATION_TOKEN_LOCK:
        cached_token = str(_INSTALLATION_TOKEN_CACHE.get("token") or "")
        cached_expires_at = _INSTALLATION_TOKEN_CACHE.get("expires_at")
        if (
            cached_token
            and isinstance(cached_expires_at, datetime)
            and cached_expires_at
            > datetime.now(UTC)
            + timedelta(seconds=GITHUB_TOKEN_REFRESH_BUFFER_SECONDS)
        ):
            return cached_token

        token, expires_at = _request_installation_access_token()
        _INSTALLATION_TOKEN_CACHE["token"] = token
        _INSTALLATION_TOKEN_CACHE["expires_at"] = expires_at
        return token


def _request_installation_access_token() -> tuple[str, datetime]:
    app_id = GITHUB_APP_ID
    installation_id = GITHUB_APP_INSTALLATION_ID
    private_key = _normalize_private_key(GITHUB_APP_PRIVATE_KEY)
    if not app_id or not installation_id or not private_key:
        raise RepositorySourceError(
            source="github",
            status="misconfigured",
            public_message="GitHub repository search is missing GitHub App credentials.",
        )

    app_jwt = _build_app_jwt(app_id=app_id, private_key=private_key)
    request = Request(
        f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {app_jwt}",
            "User-Agent": build_user_agent(),
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(request, timeout=GITHUB_AUTH_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise _build_auth_error(exc) from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise RepositorySourceError(
            source="github",
            status="error",
            public_message="GitHub repository search could not obtain an installation token.",
        ) from exc

    token = str(payload.get("token") or "").strip()
    expires_at = _parse_github_timestamp(str(payload.get("expires_at") or ""))
    if not token or expires_at is None:
        raise RepositorySourceError(
            source="github",
            status="misconfigured",
            public_message="GitHub App token exchange returned an invalid payload.",
        )

    return token, expires_at


def _build_app_jwt(*, app_id: str, private_key: str) -> str:
    now = int(time.time())
    return str(
        jwt.encode(
            {
                "iat": now - 60,
                "exp": now + 540,
                "iss": app_id,
            },
            private_key,
            algorithm="RS256",
        )
    )


def _normalize_private_key(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if "\\n" in value and "\n" not in value:
        value = value.replace("\\n", "\n")
    if not value.endswith("\n"):
        value += "\n"
    return value


def _parse_github_timestamp(raw_value: str) -> datetime | None:
    value = raw_value.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(UTC)


def _build_auth_error(exc: HTTPError) -> RepositorySourceError:
    message = _read_error_message(exc)

    if exc.code in (401, 403):
        lowered = message.casefold()
        if (
            exc.headers.get("Retry-After")
            or exc.headers.get("X-RateLimit-Remaining") == "0"
            or "rate limit" in lowered
        ):
            return RepositorySourceError(
                source="github",
                status="rate_limited",
                public_message="GitHub repository search is rate-limited right now.",
            )
        return RepositorySourceError(
            source="github",
            status="unauthorized",
            public_message="GitHub repository access is unauthorized right now.",
        )

    if exc.code == 429:
        return RepositorySourceError(
            source="github",
            status="rate_limited",
            public_message="GitHub repository search is rate-limited right now.",
        )

    return RepositorySourceError(
        source="github",
        status="error",
        public_message="GitHub repository search is unavailable right now.",
    )


def _read_error_message(exc: HTTPError) -> str:
    try:
        payload = json.load(exc)
    except Exception:
        return str(exc.reason)

    if isinstance(payload, dict):
        return str(payload.get("message") or exc.reason)
    return str(exc.reason)

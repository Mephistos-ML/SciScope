"""Authentication helpers for GitHub API requests."""

from __future__ import annotations

import json
from threading import Lock
from _thread import LockType
import time
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import jwt

from app.__version__ import __version__
from app.integrations.repositories.common.source_status import RepositorySourceError


GITHUB_API_BASE = "https://api.github.com"
GITHUB_AUTH_TIMEOUT_SECONDS = 30
GITHUB_TOKEN_REFRESH_BUFFER_SECONDS = 60
GITHUB_TOKEN_RESPONSE_MAX_BYTES = 65536



def build_user_agent() -> str:
    """Build the application user agent for outbound GitHub requests."""

    return f"SciScope/{__version__}"


@dataclass(frozen=True)
class _InstallationToken:
    value: str = field(repr=False)
    expires_at: datetime


@dataclass
class _InstallationTokenCache:
    token: _InstallationToken | None = None
    lock: LockType = field(default_factory=Lock)


@dataclass(frozen=True)
class GitHubAppAuth:
    """One installation's credentials, token cache and refresh coordination."""

    mode: str
    app_id: str
    installation_id: str
    private_key: str = field(repr=False)
    _cache: _InstallationTokenCache = field(default_factory=_InstallationTokenCache, init=False, repr=False, compare=False)

    def build_auth_headers(self) -> dict[str, str]:
        """Build required authentication headers for GitHub API requests."""

        if self.mode == "disabled":
            raise RepositorySourceError(
                source="github",
                status="disabled",
                public_message="GitHub repository search is disabled in this environment.",
            )

        if self.mode != "app":
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
                ("GITHUB_APP_ID", self.app_id),
                ("GITHUB_APP_INSTALLATION_ID", self.installation_id),
                ("GITHUB_APP_PRIVATE_KEY", self.private_key),
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

        token = self._get_installation_access_token()
        return {"Authorization": f"Bearer {token}"}

    def _get_installation_access_token(self) -> str:
        with self._cache.lock:
            cached = self._cache.token
            if cached is not None and cached.expires_at > (
                datetime.now(UTC) + timedelta(seconds=GITHUB_TOKEN_REFRESH_BUFFER_SECONDS)
            ):
                return cached.value
            token = self._request_installation_access_token()
            self._cache.token = token
            return token.value

    def _request_installation_access_token(self) -> _InstallationToken:
        app_id = self.app_id
        installation_id = self.installation_id
        private_key = _normalize_private_key(self.private_key)
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
                raw = response.read(GITHUB_TOKEN_RESPONSE_MAX_BYTES + 1)
                if len(raw) > GITHUB_TOKEN_RESPONSE_MAX_BYTES:
                    raise ValueError("GitHub installation token response exceeds its size limit.")
                payload = json.loads(raw)
        except HTTPError as exc:
            raise _build_auth_error(exc) from exc
        except (TimeoutError, URLError, OSError) as exc:
            raise RepositorySourceError(
                source="github",
                status="error",
                public_message="GitHub repository search could not obtain an installation token.",
            ) from exc
        except ValueError as exc:
            raise RepositorySourceError(
                source="github", status="misconfigured",
                public_message="GitHub App token exchange returned an invalid payload.",
            ) from exc

        try:
            if not isinstance(payload, dict) or not isinstance(payload.get("token"), str):
                raise ValueError("Invalid installation token payload.")
            token = payload["token"].strip()
            expires_at = _parse_github_timestamp(str(payload.get("expires_at") or ""))
            if not token or expires_at is None or expires_at <= datetime.now(UTC):
                raise ValueError("Invalid installation token lifetime.")
        except ValueError as exc:
            raise RepositorySourceError(
                source="github",
                status="misconfigured",
                public_message="GitHub App token exchange returned an invalid payload.",
            ) from exc

        return _InstallationToken(token, expires_at)


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
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("GitHub token expiration must include a timezone.")
    return parsed.astimezone(UTC)


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

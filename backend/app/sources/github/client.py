"""Low-level GitHub HTTP client helpers."""

from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.__version__ import __version__
from app.sources.github.auth import build_auth_headers
from app.sources.common import RepositorySourceError

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_REQUEST_TIMEOUT_SECONDS = 30
GITHUB_REQUEST_RETRIES = 3
GITHUB_RETRY_BACKOFF_SECONDS = 1.5


def build_user_agent() -> str:
    """Build the application user agent for outbound GitHub requests."""

    return f"SciScope/{__version__}"


def fetch_json(url: str) -> object:
    """Fetch one JSON payload from the GitHub API with simple retries."""

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": build_user_agent(),
        "X-GitHub-Api-Version": "2022-11-28",
    }
    headers.update(build_auth_headers())

    request = Request(
        url,
        headers=headers,
    )

    last_error: Exception | None = None
    for attempt in range(1, GITHUB_REQUEST_RETRIES + 1):
        try:
            with urlopen(request, timeout=GITHUB_REQUEST_TIMEOUT_SECONDS) as response:
                return json.load(response)
        except HTTPError as exc:
            message = _read_error_message(exc)
            if attempt < GITHUB_REQUEST_RETRIES and 500 <= exc.code < 600:
                logger.warning(
                    (
                        "GitHub API request returned retryable HTTP error "
                        "url=%s attempt=%s/%s status=%s message=%r"
                    ),
                    url,
                    attempt,
                    GITHUB_REQUEST_RETRIES,
                    exc.code,
                    message,
                )
                time.sleep(GITHUB_RETRY_BACKOFF_SECONDS * attempt)
                continue
            logger.warning(
                (
                    "GitHub API request failed "
                    "url=%s attempt=%s/%s status=%s message=%r"
                ),
                url,
                attempt,
                GITHUB_REQUEST_RETRIES,
                exc.code,
                message,
            )
            raise _build_source_error(exc) from exc
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            logger.warning(
                (
                    "GitHub API request transport error "
                    "url=%s attempt=%s/%s error_type=%s error=%r"
                ),
                url,
                attempt,
                GITHUB_REQUEST_RETRIES,
                type(exc).__name__,
                exc,
            )
            if attempt == GITHUB_REQUEST_RETRIES:
                break
            time.sleep(GITHUB_RETRY_BACKOFF_SECONDS * attempt)

    if last_error is not None:
        raise last_error

    raise RuntimeError("GitHub fetch failed without a captured error.")


def _build_source_error(exc: HTTPError) -> RepositorySourceError:
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

"""Low-level GitLab HTTP client helpers."""

from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.__version__ import __version__
from app.config import GITLAB_BASE_URL
from app.sources.gitlab.auth import build_auth_headers
from app.sources.common import RepositorySourceError

logger = logging.getLogger(__name__)

GITLAB_API_BASE = f"{GITLAB_BASE_URL.rstrip('/')}/api/v4"
GITLAB_REQUEST_TIMEOUT_SECONDS = 30
GITLAB_REQUEST_RETRIES = 3
GITLAB_RETRY_BACKOFF_SECONDS = 1.5


def build_user_agent() -> str:
    """Build the application user agent for outbound GitLab requests."""

    return f"SciScope/{__version__}"


def fetch_json(url: str) -> object:
    """Fetch one JSON payload from the GitLab API with simple retries."""

    headers = {
        "Accept": "application/json",
        "User-Agent": build_user_agent(),
    }
    headers.update(build_auth_headers())

    request = Request(
        url,
        headers=headers,
    )

    last_error: Exception | None = None
    for attempt in range(1, GITLAB_REQUEST_RETRIES + 1):
        try:
            with urlopen(request, timeout=GITLAB_REQUEST_TIMEOUT_SECONDS) as response:
                return json.load(response)
        except HTTPError as exc:
            message = _read_error_message(exc)
            if attempt < GITLAB_REQUEST_RETRIES and 500 <= exc.code < 600:
                logger.warning(
                    (
                        "GitLab API request returned retryable HTTP error "
                        "url=%s attempt=%s/%s status=%s message=%r"
                    ),
                    url,
                    attempt,
                    GITLAB_REQUEST_RETRIES,
                    exc.code,
                    message,
                )
                time.sleep(GITLAB_RETRY_BACKOFF_SECONDS * attempt)
                continue
            logger.warning(
                (
                    "GitLab API request failed "
                    "url=%s attempt=%s/%s status=%s message=%r"
                ),
                url,
                attempt,
                GITLAB_REQUEST_RETRIES,
                exc.code,
                message,
            )
            raise _build_source_error(exc) from exc
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            logger.warning(
                (
                    "GitLab API request transport error "
                    "url=%s attempt=%s/%s error_type=%s error=%r"
                ),
                url,
                attempt,
                GITLAB_REQUEST_RETRIES,
                type(exc).__name__,
                exc,
            )
            if attempt == GITLAB_REQUEST_RETRIES:
                break
            time.sleep(GITLAB_RETRY_BACKOFF_SECONDS * attempt)

    if last_error is not None:
        raise last_error

    raise RuntimeError("GitLab fetch failed without a captured error.")


def _build_source_error(exc: HTTPError) -> RepositorySourceError:
    if exc.code in (401, 403):
        return RepositorySourceError(
            source="gitlab",
            status="unauthorized",
            public_message="GitLab repository access is unauthorized right now.",
        )

    if exc.code == 429:
        return RepositorySourceError(
            source="gitlab",
            status="rate_limited",
            public_message="GitLab repository search is rate-limited right now.",
        )

    return RepositorySourceError(
        source="gitlab",
        status="error",
        public_message="GitLab repository search is unavailable right now.",
    )


def _read_error_message(exc: HTTPError) -> str:
    try:
        payload = json.load(exc)
    except Exception:
        return str(exc.reason)

    if isinstance(payload, dict):
        if isinstance(payload.get("message"), str):
            return str(payload["message"])
        error = payload.get("error")
        if isinstance(error, str):
            return error
    return str(exc.reason)

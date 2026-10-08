"""Low-level GitHub HTTP client helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar
import json
import logging
from math import ceil
import time
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.integrations.repositories.github.http import (
    GITHUB_API_BASE, build_user_agent, read_error_message,
)
from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.common.deadlines import read_remaining_timeout_seconds

logger = logging.getLogger(__name__)

GITHUB_REQUEST_TIMEOUT_SECONDS = 30
GITHUB_REQUEST_RETRIES = 3
GITHUB_RETRY_BACKOFF_SECONDS = 1.5


@dataclass(frozen=True)
class GitHubClient:
    auth_headers: Callable[[], dict[str, str]] = field(repr=False)
    api_base: ClassVar[str] = GITHUB_API_BASE

    def fetch_json(
        self,
        url: str,
        *,
        deadline_monotonic: float | None = None,
    ) -> JsonResponse:
        """Fetch JSON and the provider URL after any HTTP redirect."""

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": build_user_agent(),
            "X-GitHub-Api-Version": "2022-11-28",
        }
        headers.update(self.auth_headers())

        request = Request(
            url,
            headers=headers,
        )

        last_error: Exception | None = None
        for attempt in range(1, GITHUB_REQUEST_RETRIES + 1):
            try:
                request_timeout_seconds = read_remaining_timeout_seconds(
                    deadline_monotonic=deadline_monotonic,
                    fallback_seconds=GITHUB_REQUEST_TIMEOUT_SECONDS,
                )
                with urlopen(request, timeout=request_timeout_seconds) as response:
                    final_url = getattr(response, "geturl", lambda: url)()
                    return JsonResponse(payload=json.load(response), url=str(final_url))
            except HTTPError as exc:
                message = read_error_message(exc)
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
                raise _build_source_error(exc, message=message) from exc
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
                if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
                    break
                time.sleep(GITHUB_RETRY_BACKOFF_SECONDS * attempt)

        if last_error is not None:
            raise _build_transport_source_error(last_error) from last_error

        raise RuntimeError("GitHub fetch failed without a captured error.")


def _build_source_error(exc: HTTPError, *, message: str) -> RepositorySourceError:
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
                retry_after_seconds=_read_retry_after_seconds(exc),
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
            retry_after_seconds=_read_retry_after_seconds(exc),
        )

    return RepositorySourceError(
        source="github",
        status="error",
        public_message="GitHub repository search is unavailable right now.",
    )


def _build_transport_source_error(exc: Exception) -> RepositorySourceError:
    if _is_timeout_error(exc):
        return RepositorySourceError(
            source="github",
            status="timed_out",
            public_message="GitHub repository search timed out right now.",
        )

    return RepositorySourceError(
        source="github",
        status="error",
        public_message="GitHub repository search is unavailable right now.",
    )


def _is_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True

    if isinstance(exc, URLError) and isinstance(exc.reason, TimeoutError):
        return True

    return "timed out" in str(exc).casefold()


def _read_retry_after_seconds(exc: HTTPError) -> int | None:
    """Read a provider retry delay from rate-limit response headers."""

    retry_after = _read_positive_seconds(exc.headers.get("Retry-After"))
    if retry_after is not None:
        return retry_after

    reset_timestamp = _read_positive_seconds(exc.headers.get("X-RateLimit-Reset"))
    if reset_timestamp is None:
        return None

    return max(1, ceil(reset_timestamp - time.time()))


def _read_positive_seconds(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None

    try:
        value = ceil(float(raw_value))
    except ValueError:
        return None
    return value if value > 0 else None

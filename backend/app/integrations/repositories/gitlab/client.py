"""Low-level GitLab HTTP client helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
from http.client import HTTPException
import logging
import time
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.__version__ import __version__
from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.common.deadlines import read_remaining_timeout_seconds
from app.integrations.repositories.common.response_body import read_response_body

logger = logging.getLogger(__name__)

GITLAB_REQUEST_TIMEOUT_SECONDS = 30
GITLAB_REQUEST_RETRIES = 3
GITLAB_RETRY_BACKOFF_SECONDS = 1.5


def build_user_agent() -> str:
    """Build the application user agent for outbound GitLab requests."""

    return f"SciScope/{__version__}"


@dataclass(frozen=True)
class GitLabClient:
    base_url: str
    auth_headers: Callable[[], dict[str, str]] = field(repr=False)

    @property
    def api_base(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v4"

    def fetch_json(
        self,
        url: str,
        *,
        deadline_monotonic: float | None = None,
        max_response_bytes: int | None = None,
    ) -> JsonResponse:
        """Fetch JSON and the provider URL after any HTTP redirect."""

        if max_response_bytes is not None and max_response_bytes <= 0:
            raise ValueError("Response byte budget must be positive.")
        headers = {
            "Accept": "application/json",
            "User-Agent": build_user_agent(),
        }
        headers.update(self.auth_headers())

        request = Request(
            url,
            headers=headers,
        )

        last_error: Exception | None = None
        for attempt in range(1, GITLAB_REQUEST_RETRIES + 1):
            try:
                request_timeout_seconds = read_remaining_timeout_seconds(
                    deadline_monotonic=deadline_monotonic,
                    fallback_seconds=GITLAB_REQUEST_TIMEOUT_SECONDS,
                )
                with urlopen(request, timeout=request_timeout_seconds) as response:
                    final_url = getattr(response, "geturl", lambda: url)()
                    if max_response_bytes is None and deadline_monotonic is None:
                        payload = json.load(response)
                    else:
                        body = read_response_body(response, source="gitlab",
                                                  deadline_monotonic=deadline_monotonic,
                                                  max_response_bytes=max_response_bytes)
                        try:
                            payload = json.loads(body)
                        except (ValueError, UnicodeDecodeError, RecursionError) as error:
                            raise RepositorySourceError(source="gitlab", status="error",
                                                        public_message="Provider returned invalid JSON.") from error
                    return JsonResponse(payload=payload, url=str(final_url))
            except HTTPError as exc:
                try:
                    message = _read_error_message(exc, deadline_monotonic=deadline_monotonic)
                except TimeoutError as error:
                    raise _build_transport_source_error(error) from error
                finally:
                    exc.close()
                if (attempt < GITLAB_REQUEST_RETRIES and 500 <= exc.code < 600
                        and (deadline_monotonic is None or monotonic() + GITLAB_RETRY_BACKOFF_SECONDS * attempt < deadline_monotonic)):
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
            except (HTTPException, TimeoutError, URLError, OSError) as exc:
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
                if deadline_monotonic is not None and monotonic() + GITLAB_RETRY_BACKOFF_SECONDS * attempt >= deadline_monotonic:
                    break
                time.sleep(GITLAB_RETRY_BACKOFF_SECONDS * attempt)

        if last_error is not None:
            raise _build_transport_source_error(last_error) from last_error

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


def _build_transport_source_error(exc: Exception) -> RepositorySourceError:
    if _is_timeout_error(exc):
        return RepositorySourceError(
            source="gitlab",
            status="timed_out",
            public_message="GitLab repository search timed out right now.",
        )

    return RepositorySourceError(
        source="gitlab",
        status="error",
        public_message="GitLab repository search is unavailable right now.",
    )


def _is_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True

    if isinstance(exc, URLError) and isinstance(exc.reason, TimeoutError):
        return True

    return "timed out" in str(exc).casefold()


def _read_error_message(exc: HTTPError, *, deadline_monotonic: float | None = None) -> str:
    try:
        if deadline_monotonic is None or exc.fp is None:
            payload = json.load(exc)
        else:
            payload = json.loads(read_response_body(exc, source="gitlab",
                                                   deadline_monotonic=deadline_monotonic, max_response_bytes=64 * 1024))
    except TimeoutError:
        raise
    except (HTTPException, ValueError, TypeError, OSError, RepositorySourceError):
        return str(exc.reason)

    if isinstance(payload, dict):
        if isinstance(payload.get("message"), str):
            return str(payload["message"])
        error = payload.get("error")
        if isinstance(error, str):
            return error
    return str(exc.reason)

"""Response size limits and cancellation of blocking HTTP reads at their deadline."""

from http.client import HTTPException, HTTPResponse
import os
import socket
from threading import Timer
from time import monotonic

from app.integrations.repositories.common.source_status import RepositorySourceError


def read_response_body(
    response: HTTPResponse, *, source: str,
    deadline_monotonic: float | None, max_response_bytes: int | None,
) -> bytes:
    """Read within the byte budget; stop the socket when total read time expires."""
    limit = max_response_bytes + 1 if max_response_bytes is not None else None
    if deadline_monotonic is None:
        body = response.read(limit)
    else:
        remaining = deadline_monotonic - monotonic()
        if remaining <= 0:
            raise TimeoutError("The response read budget has expired.")
        # A socket timeout measures inactivity, not total read time. Duplicate the
        # public response descriptor so shutdown interrupts trickling/chunked reads
        # without depending on urllib's private socket layout or leaving a reader running.
        with socket.socket(fileno=os.dup(response.fileno())) as connection:
            def expire() -> None:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass  # The peer may have already closed the connection.

            timer = Timer(remaining, expire)
            timer.daemon = True
            timer.start()
            try:
                body = response.read(limit)
            except (HTTPException, OSError) as error:
                if monotonic() >= deadline_monotonic:
                    raise TimeoutError("The response read budget has expired.") from error
                raise
            finally:
                timer.cancel()
                timer.join()
        if monotonic() >= deadline_monotonic:
            raise TimeoutError("The response read budget has expired.")
    if max_response_bytes is not None and len(body) > max_response_bytes:
        raise RepositorySourceError(source=source, status="error",
                                    public_message="Provider response exceeded its byte budget.")
    return body

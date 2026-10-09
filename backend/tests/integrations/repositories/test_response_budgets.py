"""Real HTTP framing obeys deadlines and classifies interrupted response bodies."""

from http.client import HTTPResponse, IncompleteRead
from importlib import import_module
import socket
from threading import Event, Thread
from time import monotonic
from urllib.error import HTTPError

import pytest

from app.integrations.repositories.common.source_status import RepositorySourceError


@pytest.fixture
def provider_response(monkeypatch):
    stopped, disconnected = Event(), Event()
    sockets, threads = [], []

    def open_response(request, timeout):
        reader, writer = socket.socketpair()
        reader.settimeout(timeout)
        sockets.extend((reader, writer))
        path = request.full_url
        chunked = "chunked" in path or "broken" in path
        status = 503 if "error" in path else 200

        def send():
            try:
                if "complete" in path:
                    writer.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{"ok":true}')
                    return
                framing = "Transfer-Encoding: chunked" if chunked else "Content-Length: 10000"
                writer.sendall(f"HTTP/1.1 {status} Response\r\n{framing}\r\n\r\n".encode())
                if "broken" in path:
                    writer.sendall(b"5\r\nabc")
                    return
                # Each byte arrives within the inactivity timeout, including inside
                # one HTTP chunk. Only a total deadline stops this blocking read.
                writer.sendall(b"1000\r\n" if chunked else b"")
                for _ in range(300):
                    writer.sendall(b" ")
                    if stopped.wait(.01):
                        return
            except (BrokenPipeError, ConnectionResetError):
                disconnected.set()
            finally:
                writer.close()

        thread = Thread(target=send)
        threads.append(thread)
        thread.start()
        response = HTTPResponse(reader)
        response.url = request.full_url
        response.begin()
        reader.close()  # Transfer socket lifetime to the response file, as urllib does.
        if status != 200:
            raise HTTPError(request.full_url, status, "Unavailable", response.headers, response)
        return response

    for source in ("github", "gitlab"):
        module = import_module(f"app.integrations.repositories.{source}.client")
        monkeypatch.setattr(module, "urlopen", open_response)
    try:
        yield disconnected
    finally:
        stopped.set()
        for thread in threads:
            thread.join()
        for connection in sockets:
            connection.close()


def _client(source):
    module = import_module(f"app.integrations.repositories.{source}.client")
    return module.GitHubClient(lambda: {}) if source == "github" else module.GitLabClient("https://gitlab.com", lambda: {})


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_complete_response_is_delivered_within_its_read_budget(provider_response, source):
    response = _client(source).fetch_json("https://example.com/complete",
                                         deadline_monotonic=monotonic() + 2, max_response_bytes=1024)
    assert response.payload == {"ok": True}
    assert response.url == "https://example.com/complete"


@pytest.mark.parametrize("source", ["github", "gitlab"])
@pytest.mark.parametrize("framing", ["fixed", "chunked"])
@pytest.mark.parametrize("status", ["success", "error"])
def test_trickling_response_is_cancelled_at_the_total_deadline(provider_response, source, framing, status):
    started = monotonic()
    with pytest.raises(RepositorySourceError) as failure:
        _client(source).fetch_json(f"https://example.com/{framing}-{status}",
                                  deadline_monotonic=started + .2, max_response_bytes=64 * 1024)
    assert failure.value.status == "timed_out"
    assert isinstance(failure.value.__cause__, TimeoutError)
    assert monotonic() - started < 1.5  # Scheduling slack, shorter than the server's body.
    assert provider_response.wait(1), "The timed-out HTTP read left its connection open."


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_interrupted_chunked_response_is_a_classified_transport_failure(provider_response, monkeypatch, source):
    module = import_module(f"app.integrations.repositories.{source}.client")
    monkeypatch.setattr(module.time, "sleep", lambda _delay: None)
    with pytest.raises(RepositorySourceError) as failure:
        _client(source).fetch_json("https://example.com/broken", max_response_bytes=1024)
    assert failure.value.status == "error"
    assert isinstance(failure.value.__cause__, IncompleteRead)

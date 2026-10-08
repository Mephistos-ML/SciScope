"""Siteverify request contract and fail-closed response handling."""

from contextlib import contextmanager
from urllib.parse import parse_qs
from uuid import UUID

import pytest

from app.integrations.security.cloudflare import turnstile


def respond(monkeypatch, body):
    @contextmanager
    def open_response(request, *, timeout):
        class Response:
            def read(self, limit):
                return body[:limit]
        yield Response()
    monkeypatch.setattr(turnstile, "urlopen", open_response)


def verify():
    return turnstile.verify_turnstile_token("proof", secret_key="secret", timeout_seconds=3, remote_ip="192.0.2.1")


def test_siteverify_request_and_success_mapping(monkeypatch):
    captured = {}

    @contextmanager
    def open_response(request, *, timeout):
        captured.update(url=request.full_url, method=request.method, form=parse_qs(request.data.decode()), timeout=timeout)
        class Response:
            def read(self, limit):
                return b'{"success":true}'
        yield Response()

    monkeypatch.setattr(turnstile, "urlopen", open_response)
    assert verify().success
    assert captured["url"] == turnstile.TURNSTILE_SITEVERIFY_URL
    assert captured["method"] == "POST"
    assert captured["timeout"] == 3
    assert captured["form"]["secret"] == ["secret"]
    assert captured["form"]["response"] == ["proof"]
    assert captured["form"]["remoteip"] == ["192.0.2.1"]
    UUID(captured["form"]["idempotency_key"][0])


def test_rejected_proof_is_distinct_from_provider_outage(monkeypatch):
    respond(monkeypatch, b'{"success":false,"error-codes":["invalid-input-response"]}')
    result = verify()
    assert not result.success and not result.service_unavailable
    assert result.error_codes == ("invalid-input-response",)


@pytest.mark.parametrize("body", [
    b"invalid json", b"\xff", b"[]", b"{}", b'{"success":"false"}',
    b'{"success":1}', b'{"success":true,"error-codes":null}',
    b'{"success":true,"error-codes":[1]}',
    b"x" * (turnstile.TURNSTILE_MAX_RESPONSE_BYTES + 1),
])
def test_unusable_provider_response_cannot_authorize_request(monkeypatch, body):
    respond(monkeypatch, body)
    result = verify()
    assert not result.success and result.service_unavailable
    assert result.error_codes == ("internal-error",)


def test_timeout_is_unavailable_verification(monkeypatch):
    def timeout(*args, **kwargs):
        raise TimeoutError("provider diagnostics")
    monkeypatch.setattr(turnstile, "urlopen", timeout)
    result = verify()
    assert not result.success and result.service_unavailable

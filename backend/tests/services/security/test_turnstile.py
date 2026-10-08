"""Anti-abuse policy must decide whether external verification is needed."""

import pytest

from app.models.security import TurnstileVerificationResult
from app.services.security.turnstile import verify_turnstile_token


@pytest.mark.parametrize("enabled,token,success,code", [
    (False, "", True, ()),
    (True, " ", False, ("missing-input-response",)),
    (True, "x" * 2049, False, ("invalid-input-response",)),
])
def test_policy_short_circuits_without_external_io(enabled, token, success, code):
    def verify(*args, **kwargs):
        pytest.fail("This policy outcome must not call the provider")
    result = verify_turnstile_token(token, enabled=enabled, verify=verify)
    assert result.success is success
    assert result.error_codes == code


def test_valid_proof_is_normalized_and_preserves_provider_outcome():
    outcome = TurnstileVerificationResult(False, ("internal-error",), service_unavailable=True)
    def verify(token, *, remote_ip):
        assert token == "proof"
        assert remote_ip == "192.0.2.1"
        return outcome
    assert verify_turnstile_token(" proof ", enabled=True, verify=verify, remote_ip="192.0.2.1") == outcome

"""Scientific context invariants apply outside HTTP as well."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.models.scientific_domain import parse_scientific_domain, ScientificDomain
from app.models.search_run import SearchRun


@pytest.mark.parametrize("value", ["", "unknown", "Chemistry", 1, True, [], {}])
def test_invalid_domain_cannot_enter_a_run(value):
    run = SearchRun("run", None, "topic", "hash", "queued", "bootstrap", None, None,
                    "policy", "revision", datetime.now(UTC))
    with pytest.raises(ValueError):
        replace(run, scientific_domain=value)


def test_optional_domain_uses_stable_identity():
    assert parse_scientific_domain(None) is None
    assert parse_scientific_domain("chemistry") is ScientificDomain.CHEMISTRY

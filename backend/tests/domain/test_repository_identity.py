"""Canonical identities obey the same native-ID contract at creation and parsing."""

import pytest

from app.models.repository import build_repository_id, parse_repository_id


@pytest.mark.parametrize("provider_id", ["", "0", "000", "-1", "+1", "1.5", "١٢٣", "owner/tool", "123?x=y"])
def test_invalid_native_identity_cannot_be_built_or_parsed(provider_id):
    with pytest.raises(ValueError):
        build_repository_id("github", provider_id)
    with pytest.raises(ValueError):
        parse_repository_id(f"github:repo:{provider_id}", source="github")


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_identity_round_trip_preserves_native_id_and_checks_source(source):
    repository_id = build_repository_id(source.upper(), " 123 ")
    assert repository_id == f"{source}:repo:123"
    assert parse_repository_id(repository_id, source=source) == "123"
    with pytest.raises(ValueError):
        parse_repository_id(repository_id, source="other")

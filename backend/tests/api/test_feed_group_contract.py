"""Check the grouped Feed client DTOs against the actual HTTP response schemas."""

from pathlib import Path
import re

import pytest

from app.api.routes.feed_groups import (
    FeedGroupDetailResponse, FeedGroupResponse, FeedGroupsResponse, FeedMemberResponse, FeedReleaseResponse,
)

CLIENT_TYPES = {
    "FeedMemberResponse": "FeedEventItem",
    "FeedReleaseResponse": "FeedReleasePayload",
    "FeedGroupResponse": "FeedGroupItem",
    "FeedGroupsResponse": "FeedGroupListPayload",
    "FeedGroupDetailResponse": "FeedGroupDetailPayload",
}


def _client_fields(name: str, source: str) -> dict[str, str]:
    declaration = re.search(rf"export type {name} = (?:(\w+) & )?\{{([^}}]+)\}};", source)
    assert declaration is not None, f"Missing client response type: {name}"
    inherited, body = declaration.groups()
    fields = _client_fields(inherited, source) if inherited else {}
    fields.update(re.findall(r"^\s*(\w+): (.+);$", body, re.MULTILINE))
    return fields


def _client_type(schema: dict) -> str:
    if "$ref" in schema:
        return CLIENT_TYPES[schema["$ref"].rsplit("/", 1)[-1]]
    if "anyOf" in schema:
        return " | ".join(_client_type(item) for item in schema["anyOf"])
    if "enum" in schema:
        return " | ".join(f'"{item}"' for item in schema["enum"])
    if schema["type"] == "array":
        return _client_type(schema["items"]) + "[]"
    return {"string": "string", "integer": "number", "boolean": "boolean", "null": "null",
            "object": "Record<string, unknown>"}[schema["type"]]


@pytest.mark.parametrize("response", (FeedMemberResponse, FeedReleaseResponse, FeedGroupResponse,
                                     FeedGroupsResponse, FeedGroupDetailResponse))
def test_grouped_feed_client_fields_types_and_nullability_match_http(response):
    source = (Path(__file__).resolve().parents[3] / "frontend/src/types/api.ts").read_text()
    fields = _client_fields(CLIENT_TYPES[response.__name__], source)
    schema = response.model_json_schema()
    assert set(fields) == set(schema["properties"]) == set(schema["required"])
    for name, definition in schema["properties"].items():
        assert set(fields[name].split(" | ")) == set(_client_type(definition).split(" | ")), name

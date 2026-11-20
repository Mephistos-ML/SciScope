"""Outgoing queries are whole literal phrases on every provider search channel."""

from urllib.parse import parse_qs, urlsplit

import pytest

from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.common.search_query import quote_search_phrase
from app.integrations.repositories.github.search import code as github_code
from app.integrations.repositories.github.search.file_policy import CODE_SEARCH_EXTENSION_SUFFIX
from app.integrations.repositories.github.search import repository as github_repository
from app.integrations.repositories.gitlab.search import code as gitlab_code
from app.integrations.repositories.gitlab.search import repository as gitlab_repository
from tests.fixtures.repository_clients import make_repository_client


@pytest.mark.parametrize("query, expected", [
    ("paramagnetic nmr", '"paramagnetic nmr"'),
    ('"paramagnetic nmr"', '"paramagnetic nmr"'),
    ("  paramagnetic nmr  ", '"paramagnetic nmr"'),
    ('a "quoted" method', '"a \\"quoted\\" method"'),
    (r"method\file", '"method\\\\file"'),
    ('"one" OR "two"', '"\\"one\\" OR \\"two\\""'),
])
def test_whole_query_is_a_single_escaped_phrase(query, expected):
    assert quote_search_phrase(query) == expected


@pytest.mark.parametrize("query", ["", " ", '""', '"  "'])
def test_empty_phrases_are_rejected(query):
    with pytest.raises(ValueError, match="must not be empty"):
        quote_search_phrase(query)


@pytest.mark.parametrize("source, channel, discover", [
    ("github", "repository_search", github_repository.discover_repository_candidates),
    ("github", "code_search", github_code.discover_repository_candidates_from_code),
    ("gitlab", "repository_search", gitlab_repository.discover_repository_candidates),
    ("gitlab", "code_search", gitlab_code.discover_repository_candidates_from_code),
])
@pytest.mark.parametrize("query", [
    "paramagnetic nmr",
    "PDS labels Python",
    "finite element solver",
    'method "quoted"',
    "x" * 185,
])
def test_only_github_code_search_receives_the_file_scope(
    monkeypatch, source, channel, discover, query,
):
    client = make_repository_client(source)
    requests = []

    def fetch(url, **kwargs):
        requests.append(url)
        return JsonResponse({"items": []} if source == "github" else [], url)

    monkeypatch.setattr(client, "fetch_json", fetch)
    assert discover([query], client=client) == []
    assert len(requests) == 1
    params = parse_qs(urlsplit(requests[0]).query)
    expected = quote_search_phrase(query)
    if source == "github" and channel == "code_search":
        expected += f" {CODE_SEARCH_EXTENSION_SUFFIX}"
    assert params["q" if source == "github" else "search"] == [expected]
    if source == "gitlab":
        assert params["scope"] == ["projects" if channel == "repository_search" else "blobs"]

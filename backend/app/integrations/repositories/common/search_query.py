# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Literal phrase syntax for outgoing repository-provider search requests.

Canonical queries and evidence identities remain unquoted application values.
Providers interpret the quoted expression according to their search engine.
"""

import re

SEARCH_QUERY_MODE = "quoted_phrase"


def quote_search_phrase(query: str) -> str:
    """Quote one whole query, escaping syntax without enabling query operators."""
    phrase = query.strip()
    if not phrase:
        raise ValueError("Search phrase must not be empty")
    if re.fullmatch(r'"(?:[^"\\]|\\["\\])*"', phrase):
        if not phrase[1:-1].strip():
            raise ValueError("Search phrase must not be empty")
        return phrase
    return '"' + phrase.replace('\\', '\\\\').replace('"', '\\"') + '"'

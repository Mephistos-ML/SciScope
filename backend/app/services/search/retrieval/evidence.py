# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Canonical retrieval evidence classification."""

from __future__ import annotations

import re

from app.models.signal import Signal
from app.services.search.retrieval.models import (
    RepositoryCandidate,
    RetrievalHit,
    RetrievalMatchEvidence,
    RetrievalMatchLocation,
)


_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "based",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "the",
        "to",
        "with",
    }
)
_README_NAMES = frozenset(
    {
        "readme",
        "readme.md",
        "readme.rst",
        "readme.txt",
        "readme.markdown",
        "readme.adoc",
        "readme.asciidoc",
    }
)
_DOCUMENTATION_SEGMENTS = frozenset({"doc", "docs", "documentation"})
_DOCUMENT_EXTENSIONS = (".md", ".markdown", ".rst", ".adoc", ".asciidoc")
_LEGAL_NAMES = frozenset({"license", "licence", "copying", "notice", "copyright"})
_DOCUMENT_NAMES = frozenset(
    {
        "changelog",
        "changes",
        "history",
        "contributing",
        "code_of_conduct",
        "security",
        "support",
        "authors",
        "install",
    }
)
_PROJECT_METADATA_NAMES = frozenset(
    {
        "citation.cff",
        "citation.bib",
        "codemeta.json",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "pipfile",
        "pipfile.lock",
        "cargo.toml",
        "cargo.lock",
        "go.mod",
        "go.sum",
        "environment.yml",
        "environment.yaml",
    }
)
_NOTEBOOK_EXTENSIONS = (".ipynb", ".qmd", ".rmd")
_CONFIGURATION_EXTENSIONS = (
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
)
_DATA_EXTENSIONS = (
    ".csv",
    ".tsv",
    ".parquet",
    ".h5",
    ".hdf5",
    ".fits",
    ".fit",
    ".fts",
    ".nc",
    ".netcdf",
    ".npy",
    ".npz",
    ".xyz",
    ".pdb",
    ".sdf",
    ".mol",
    ".mol2",
    ".cif",
)
_CODE_EXTENSIONS = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".cu",
        ".f",
        ".f90",
        ".f95",
        ".f03",
        ".for",
        ".go",
        ".h",
        ".hpp",
        ".java",
        ".jl",
        ".js",
        ".kt",
        ".lua",
        ".m",
        ".mm",
        ".php",
        ".pl",
        ".py",
        ".r",
        ".rb",
        ".rs",
        ".scala",
        ".sh",
        ".swift",
        ".ts",
        ".tsx",
    }
)


def build_retrieval_match_evidence(hit: RetrievalHit) -> RetrievalMatchEvidence:
    """Classify one raw retrieval hit into a source-independent match location."""

    signal = hit.signal
    query = hit.query.strip()
    path = str(signal.payload.get("matched_path") or "").strip()
    # A file hit is evidence in that file even when its repository metadata also
    # contains the query. Do not turn many code hits into description matches.
    location = (
        classify_match_path(path, fallback=hit.channel)
        if path
        else _classify_metadata_location(signal, query)
    )
    if location is None:
        location = classify_match_path(path, fallback=hit.channel)

    return RetrievalMatchEvidence(
        query=query,
        location=location,
        path=path,
        channel=hit.channel,
        origin="provider",
        retrieval_rank=hit.rank,
    )


def count_current_query_matches(
    candidate: RepositoryCandidate,
    queries: tuple[str, ...] | list[str],
) -> int:
    """Count only query evidence belonging to the current search run."""

    current_queries = {normalize_query(query) for query in queries if query.strip()}
    return len(
        {
            normalize_query(query)
            for query in candidate.provenance.matched_queries
            if query.strip() and normalize_query(query) in current_queries
        }
    )


def normalize_query(query: str) -> str:
    """Normalize query identity for coverage comparisons."""

    return " ".join(query.casefold().split())


def _classify_metadata_location(
    signal: Signal,
    query: str,
) -> RetrievalMatchLocation | None:
    if _contains_query(signal.title, query):
        return "name"

    description = str(signal.payload.get("description") or "")
    if _contains_query(description, query):
        return "description"

    topics = signal.payload.get("topics", [])
    topics_text = (
        " ".join(str(topic).strip() for topic in topics if str(topic).strip())
        if isinstance(topics, list)
        else ""
    )
    if _contains_query(topics_text, query):
        return "topic"

    return None


def classify_match_path(
    path: str,
    *,
    fallback: str,
) -> RetrievalMatchLocation:
    """Classify a provider file path, also when replaying historical evidence."""

    normalized_path = path.strip().replace("\\", "/").casefold()
    path_parts = tuple(part for part in normalized_path.split("/") if part)
    filename = path_parts[-1] if path_parts else ""

    # Explicit file roles take precedence over generic directory/extension rules.
    # JSON/XML/TXT alone are ambiguous and deliberately do not imply data/config.
    stem = filename.rsplit(".", 1)[0]
    if filename in _LEGAL_NAMES or (
        stem in _LEGAL_NAMES and filename.endswith((*_DOCUMENT_EXTENSIONS, ".txt"))
    ):
        return "legal"
    if filename in _PROJECT_METADATA_NAMES or (
        filename.startswith("requirements") and filename.endswith(".txt")
    ):
        return "project_metadata"
    if filename in _README_NAMES:
        return "readme"
    if any(part in _DOCUMENTATION_SEGMENTS for part in path_parts[:-1]):
        return "documentation"
    if filename.endswith(_NOTEBOOK_EXTENSIONS):
        return "notebook"
    if any(filename.endswith(extension) for extension in _CODE_EXTENSIONS):
        return "code"
    if filename in {"dockerfile", "compose.json"} or filename.startswith("dockerfile."):
        return "configuration"
    if filename.endswith(_CONFIGURATION_EXTENSIONS):
        return "configuration"
    if filename.endswith(_DATA_EXTENSIONS):
        return "data"
    if (
        filename.endswith(_DOCUMENT_EXTENSIONS)
        or filename in _DOCUMENT_NAMES
        or (stem in _DOCUMENT_NAMES and filename.endswith(".txt"))
    ):
        return "documentation"
    if normalized_path:
        return "other"
    if fallback == "repository_search":
        return "metadata"
    return "other"


def _contains_query(text: str, query: str) -> bool:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return False
    return query_tokens.issubset(set(_tokenize(text)))


def _tokenize(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _WORD_PATTERN.findall(text.casefold())
        if token not in _STOP_WORDS
    )

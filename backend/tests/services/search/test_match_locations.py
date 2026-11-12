# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Taxonomy, precedence, and replay of provider-reported file matches."""

from dataclasses import replace
from math import log1p
from typing import get_args

import pytest

from app.services.search.ranking import rank_repository_candidates
from app.services.search.ranking.score import LOCATION_WEIGHTS
from app.services.search.retrieval.evidence import classify_match_path
from app.services.search.retrieval.models import (
    RetrievalMatchEvidence,
    RetrievalMatchLocation,
)
from tests.fixtures.explore import (
    build_explore_repository_signal,
    build_retrieved_candidates,
)


@pytest.mark.parametrize(
    "path,expected",
    [
        ("README.md", "readme"),
        ("README.markdown", "readme"),
        ("docs/README.md", "readme"),
        ("docs/tutorial.ipynb", "documentation"),
        ("docs/LICENSE.txt", "legal"),
        ("docs/CITATION.cff", "project_metadata"),
        ("docs/pyproject.toml", "project_metadata"),
        ("docs/example.py", "documentation"),
        ("analysis.ipynb", "notebook"),
        ("reports/study.QMD", "notebook"),
        ("experiment.Rmd", "notebook"),
        ("data/results.csv", "data"),
        ("observations.fits", "data"),
        ("molecule.xyz", "data"),
        ("output.h5", "data"),
        ("config/settings.yaml", "configuration"),
        ("settings.toml", "configuration"),
        ("Dockerfile", "configuration"),
        ("Dockerfile.dev", "configuration"),
        ("pyproject.toml", "project_metadata"),
        ("setup.py", "project_metadata"),
        ("package.json", "project_metadata"),
        ("requirements-dev.txt", "project_metadata"),
        ("environment.yml", "project_metadata"),
        ("CITATION.cff", "project_metadata"),
        ("LICENSE", "legal"),
        ("COPYING.md", "legal"),
        ("NOTICE", "legal"),
        ("CHANGELOG.md", "documentation"),
        ("CONTRIBUTING.txt", "documentation"),
        ("guide.rst", "documentation"),
        ("src/main.py", "code"),
        ("unknown.bin", "other"),
        ("arbitrary.json", "other"),
        ("arbitrary.xml", "other"),
        ("notes.txt", "other"),
        (" DOCS\\Guide.md ", "documentation"),
    ],
)
def test_file_location_classification(path, expected):
    assert classify_match_path(path, fallback="code_search") == expected


@pytest.mark.parametrize(
    "path,channel,expected",
    [
        ("", "repository_search", "metadata"),
        ("", "code_search", "other"),
        ("   ", "repository_search", "metadata"),
        ("", "unknown", "other"),
    ],
)
def test_missing_path_fallback(path, channel, expected):
    assert classify_match_path(path, fallback=channel) == expected


def test_every_location_has_an_explicit_weight():
    assert set(LOCATION_WEIGHTS) == set(get_args(RetrievalMatchLocation))


def test_historical_other_hits_are_recounted_by_the_current_taxonomy():
    candidate = build_retrieved_candidates(
        build_explore_repository_signal("github:repo:1", query="science"),
        source_statuses=(),
        successful_source_count=1,
    ).candidates[0]
    historical = RetrievalMatchEvidence("science", "other", path="analysis.ipynb")
    candidate = replace(
        candidate,
        provenance=replace(
            candidate.provenance,
            match_evidence=(
                historical,
                replace(historical, location="notebook", origin="catalog"),
                RetrievalMatchEvidence("science", "other", path="results.csv"),
            ),
        ),
    )
    ranked = rank_repository_candidates(
        (candidate,), queries=("science",)
    ).ranked_candidates[0]
    assert {
        item.location: item.count for item in ranked.features.match_counts_by_location
    } == {
        "notebook": 1,
        "data": 1,
    }
    assert ranked.score == pytest.approx(0.5 * log1p(1))
    assert ranked.score_breakdown.formula == "location_weighted_log_matches_v2"

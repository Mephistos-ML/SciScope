"""Tests for the first seeded GitHub-style matching flow."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.signal import RawSignal
from app.services.search.matching import match_signal_to_profile
from app.services.search.normalization import normalize_raw_signal
from tests.fixtures.profiles import PNMR_PROFILE


def _build_raw_signal(
    *,
    item_id: str,
    title: str,
    raw_text: str,
    files: list[str],
) -> RawSignal:
    return RawSignal(
        source="github",
        source_type="github_commit",
        item_id=item_id,
        title=title,
        url=f"https://github.com/Mephistos-ML/paranmr/commit/{item_id}",
        published_at=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
        raw_text=raw_text,
        payload={
            "signal_kind": "github_commit",
            "repo": "Mephistos-ML/paranmr",
            "files": files,
        },
    )


def test_seeded_paranmr_signal_matches_pnmr_profile() -> None:
    raw_signal = _build_raw_signal(
        item_id="demo",
        title="Add PCS tensor fitting improvements",
        raw_text=(
            "Improves susceptibility tensor fitting and automated PCS "
            "assignment workflow for paramagnetic NMR datasets."
        ),
        files=[
            "paranmr/core/fitting/tensor.py",
            "paranmr/app/pipelines/assignment.py",
        ],
    )

    normalized_signal = normalize_raw_signal(raw_signal)
    match = match_signal_to_profile(normalized_signal, PNMR_PROFILE)

    assert match.matched is True
    assert match.score > 0.0
    assert "pcs" in tuple(term.casefold() for term in match.matched_terms)


def test_related_signal_still_matches_with_lower_specificity() -> None:
    raw_signal = _build_raw_signal(
        item_id="demo-related",
        title="Refine lanthanide assignment helper",
        raw_text=(
            "Updates automated assignment logic for lanthanide-tagged protein "
            "datasets and improves structure refinement outputs."
        ),
        files=[
            "paranmr/app/pipelines/assignment.py",
            "paranmr/core/structure/refinement.py",
        ],
    )

    normalized_signal = normalize_raw_signal(raw_signal)
    match = match_signal_to_profile(normalized_signal, PNMR_PROFILE)

    assert match.matched is True
    assert match.score > 0.0
    assert "assignment" in tuple(term.casefold() for term in match.matched_terms)


def test_irrelevant_signal_is_rejected() -> None:
    raw_signal = _build_raw_signal(
        item_id="demo-irrelevant",
        title="Improve battery polymer electrolyte workflow",
        raw_text=(
            "Adds analysis utilities for solid state battery polymer "
            "electrolyte simulations and general MRI export helpers."
        ),
        files=[
            "paranmr/app/battery/electrolyte.py",
            "paranmr/app/imaging/mri_export.py",
        ],
    )

    normalized_signal = normalize_raw_signal(raw_signal)
    match = match_signal_to_profile(normalized_signal, PNMR_PROFILE)

    assert match.matched is False
    assert match.score == 0.0
    assert "solid state battery" in tuple(
        term.casefold() for term in match.excluded_terms
    )

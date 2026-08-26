"""Tests for the first seeded GitHub-style matching flow."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.signal import Signal
from app.services.search.explore.matching import match_signal_to_terms


PNMR_QUERY_TERMS = (
    "susceptibility tensor",
    "paramagnetic nmr",
    "structure refinement",
)


def _build_raw_signal(
    *,
    item_id: str,
    title: str,
    raw_text: str,
    files: list[str],
) -> Signal:
    return Signal(
        source="github",
        kind="commit",
        item_id=item_id,
        title=title,
        url=f"https://github.com/Mephistos-ML/paranmr/commit/{item_id}",
        published_at=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
        raw_text=raw_text,
        payload={
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

    match = match_signal_to_terms(raw_signal, PNMR_QUERY_TERMS)

    assert match.matched is True
    assert match.score > 0.0
    assert "susceptibility tensor" in tuple(
        term.casefold() for term in match.matched_terms
    )


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

    match = match_signal_to_terms(raw_signal, PNMR_QUERY_TERMS)

    assert match.matched is True
    assert match.score > 0.0
    assert "structure refinement" in tuple(
        term.casefold() for term in match.matched_terms
    )


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

    match = match_signal_to_terms(raw_signal, PNMR_QUERY_TERMS)

    assert match.matched is False
    assert match.score == 0.0
    assert match.matched_terms == ()
    assert match.reason == "No profile terms matched."

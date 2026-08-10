"""Static research-profile fixtures for backend tests."""

from __future__ import annotations

from app.models.topic import ResearchProfile, ResearchTopic


PNMR_TOPIC = ResearchTopic(
    slug="pnmr",
    label="Paramagnetic NMR",
    description=(
        "Paramagnetic NMR methods, susceptibility tensor fitting, PCS/PRE "
        "analysis, assignment workflows, and related scientific software."
    ),
)


PNMR_PROFILE = ResearchProfile(
    topic_slug="pnmr",
    core_terms=(
        "paramagnetic nmr",
        "pseudocontact shift",
        "pcs",
        "magnetic susceptibility tensor",
        "susceptibility tensor",
    ),
    synonyms=(
        "para nmr",
        "tensor fitting",
        "pcs fitting",
        "pre fitting",
        "delta chi",
        "anisotropy tensor",
    ),
    related_terms=(
        "assignment",
        "automated assignment",
        "spectral assignment",
        "spin label",
        "hyperfine",
        "metal center",
        "ab initio",
        "structure refinement",
        "nmr restraint",
    ),
    negative_terms=(
        "solid state battery",
        "polymer electrolyte",
        "pet imaging",
        "general mri",
        "epr only",
    ),
    seed_queries=(
        "paramagnetic NMR susceptibility tensor fitting",
        "PCS PRE lanthanide assignment",
        "paramagnetic NMR software release",
    ),
    metadata={
        "demo": "pnmr",
    },
)

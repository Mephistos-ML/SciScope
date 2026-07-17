"""Research topic to research profile generation lives here."""

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
        "paramagnetic relaxation enhancement",
        "pre",
        "magnetic susceptibility tensor",
        "susceptibility tensor",
        "lanthanide tag",
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
        "focus_repos": [
            "Mephistos-ML/paranmr",
            "henryorton/paramagpy",
        ],
        "focus_signal_kinds": [
            "github_release",
            "github_tag",
            "github_commit",
            "github_pull_request",
        ],
        "focus_files": [
            "pcs",
            "pre",
            "tensor",
            "fit",
            "assign",
        ],
        "focus_packages": [
            "paranmr",
            "paramagpy",
        ],
    },
)

def get_seed_topic(topic_slug: str) -> ResearchTopic:
    """Return a built-in topic seed for early V0 development."""

    if topic_slug == PNMR_TOPIC.slug:
        return PNMR_TOPIC

    raise KeyError(f"Unknown seeded topic: {topic_slug}")


def get_seed_profile(topic_slug: str) -> ResearchProfile:
    """Return a built-in research profile for early V0 development."""

    if topic_slug == PNMR_PROFILE.topic_slug:
        return PNMR_PROFILE

    raise KeyError(f"Unknown seeded profile: {topic_slug}")

from app.models.signal import Signal
from app.services.search.admission import run_repository_admission
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
)


def test_repository_admission_keeps_code_like_candidate() -> None:
    candidate = _build_candidate(
        item_id="github:repo:thermotools/lammps_mie_fh",
        title="thermotools/lammps_mie_fh",
        raw_text=(
            "thermotools/lammps_mie_fh\n"
            "LAMMPS package for Mie-FH simulations.\n"
            "Matched code path: src/pair_mie_fh.cpp"
        ),
        language="C++",
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="shadow")

    assert result.kept_count == 1
    assert result.rejected_count == 0
    assert result.visible_candidates[0].admission.decision == "keep"


def test_repository_admission_rejects_docs_like_weak_candidate() -> None:
    candidate = _build_candidate(
        item_id="github:repo:docs-only/orca-notes",
        title="docs-only/orca-notes",
        raw_text=(
            "docs-only/orca-notes\n"
            "ORCA notes dataset\n"
            "Matched code path: README.md"
        ),
        language="",
        topics=("notes",),
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="shadow")

    assert result.kept_count == 0
    assert result.rejected_count == 1
    assert result.visible_candidates[0].admission.decision == "reject"


def test_repository_admission_enforced_mode_hides_rejected_candidates() -> None:
    strong_candidate = _build_candidate(
        item_id="github:repo:thermotools/lammps_mie_fh",
        title="thermotools/lammps_mie_fh",
        raw_text=(
            "thermotools/lammps_mie_fh\n"
            "LAMMPS package for Mie-FH simulations.\n"
            "Matched code path: src/pair_mie_fh.cpp"
        ),
        language="C++",
        matched_channels=("code_search",),
    )
    weak_candidate = _build_candidate(
        item_id="github:repo:docs-only/orca-notes",
        title="docs-only/orca-notes",
        raw_text=(
            "docs-only/orca-notes\n"
            "ORCA notes dataset\n"
            "Matched code path: README.md"
        ),
        language="",
        topics=("notes",),
        matched_channels=("code_search",),
    )

    result = run_repository_admission(
        (strong_candidate, weak_candidate),
        mode="enforced",
    )

    assert result.kept_count == 1
    assert result.rejected_count == 1
    assert len(result.visible_candidates) == 1
    assert result.visible_candidates[0].candidate.repository_id == strong_candidate.repository_id


def _build_candidate(
    *,
    item_id: str,
    title: str,
    raw_text: str,
    language: str,
    topics: tuple[str, ...] = (),
    matched_channels: tuple[str, ...] = ("repository_search",),
) -> RepositoryCandidate:
    signal = Signal(
        source="github",
        kind="repository",
        item_id=item_id,
        title=title,
        url=f"https://github.com/{title}",
        published_at=None,
        raw_text=raw_text,
        payload={
            "repo": title,
            "query": "orca parser",
            "topics": list(topics),
            "language": language,
            "stars": 0,
        },
    )
    return RepositoryCandidate(
        repository_id=item_id,
        signal=signal,
        provenance=CandidateProvenance(
            matched_queries=("orca parser",),
            matched_channels=matched_channels,
            best_rank_by_channel={channel_name: 1 for channel_name in matched_channels},
            hit_count=len(matched_channels),
        ),
    )

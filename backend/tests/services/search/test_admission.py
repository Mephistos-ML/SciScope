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

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 1
    assert result.rejected_count == 0
    assert result.evaluated_candidates[0].admission.decision == "keep"
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "strong"


def test_repository_admission_keeps_fortran_code_match() -> None:
    candidate = _build_candidate(
        item_id="github:repo:materials/phonon-solver",
        title="materials/phonon-solver",
        raw_text=(
            "materials/phonon-solver\n"
            "Fortran solver for phonon calculations.\n"
            "Matched code path: src/dynamical_matrix.f95"
        ),
        language="Fortran",
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 1
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "strong"


def test_repository_admission_keeps_cuda_code_match() -> None:
    candidate = _build_candidate(
        item_id="github:repo:chem/gpu-kernels",
        title="chem/gpu-kernels",
        raw_text=(
            "chem/gpu-kernels\n"
            "GPU kernels for molecular simulation.\n"
            "Matched code path: src/pair_kernel.cu"
        ),
        language="C++",
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 1
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "strong"


def test_repository_admission_keeps_manifest_match() -> None:
    candidate = _build_candidate(
        item_id="github:repo:science/env-managed-tool",
        title="science/env-managed-tool",
        raw_text=(
            "science/env-managed-tool\n"
            "Scientific workflow package.\n"
            "Matched code path: environment.yml"
        ),
        language="Python",
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 1
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "strong"


def test_repository_admission_keeps_readme_match_for_real_software_repo() -> None:
    candidate = _build_candidate(
        item_id="github:repo:xudonglirpi/QEQDL",
        title="xudonglirpi/QEQDL",
        raw_text=(
            "xudonglirpi/QEQDL\n"
            "Quantum-corrected LAMMPS extension.\n"
            "Matched code path: README.md"
        ),
        language="C++",
        topics=("lammps", "molecular-simulation"),
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 1
    assert result.rejected_count == 0
    assert result.evaluated_candidates[0].admission.decision == "keep"
    assert (
        result.evaluated_candidates[0].admission.evidence.path_strength
        == "descriptive"
    )


def test_repository_admission_rejects_metadata_mirror_repo() -> None:
    candidate = _build_candidate(
        item_id="github:repo:HeinrichHartmann/arxiv_meta",
        title="HeinrichHartmann/arxiv_meta",
        raw_text=(
            "HeinrichHartmann/arxiv_meta\n"
            "Arxiv metadata mirror."
        ),
        language="",
        matched_channels=("repository_search",),
    )
    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 0
    assert result.rejected_count == 1
    assert result.evaluated_candidates[0].admission.decision == "reject"
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "none"


def test_repository_admission_keeps_benchmark_heavy_scientific_software_repo() -> None:
    candidate = _build_candidate(
        item_id="github:repo:Zhyrek/GEAM",
        title="Zhyrek/GEAM",
        raw_text=(
            "Zhyrek/GEAM\n"
            "GEAM interatomic potential for LAMMPS: CPU + Kokkos GPU pair styles, "
            "benchmarks, and validation suite."
        ),
        language="C++",
        matched_channels=("repository_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 1
    assert result.rejected_count == 0
    assert result.evaluated_candidates[0].admission.decision == "keep"


def test_repository_admission_keeps_software_repo_with_paper_mentions_in_metadata() -> None:
    candidate = _build_candidate(
        item_id="github:repo:chemistry/qm-workbench",
        title="chemistry/qm-workbench",
        raw_text=(
            "chemistry/qm-workbench\n"
            "Quantum chemistry workbench with citation support for academic papers."
        ),
        language="Python",
        matched_channels=("repository_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 1
    assert result.rejected_count == 0
    assert result.evaluated_candidates[0].admission.decision == "keep"


def test_repository_admission_rejects_paper_list_repo_name() -> None:
    candidate = _build_candidate(
        item_id="github:repo:52CV/ICCV-2021-Papers",
        title="52CV/ICCV-2021-Papers",
        raw_text=(
            "52CV/ICCV-2021-Papers\n"
            "A curated list of ICCV 2021 papers."
        ),
        language="Python",
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 0
    assert result.rejected_count == 1
    assert result.evaluated_candidates[0].admission.decision == "reject"
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "none"


def test_repository_admission_rejects_arxiv_digest_repo_name() -> None:
    candidate = _build_candidate(
        item_id="github:repo:iphysresearch/gw-arxiv-digest",
        title="iphysresearch/gw-arxiv-digest",
        raw_text=(
            "iphysresearch/gw-arxiv-digest\n"
            "Digest feed for arXiv papers in gravitational-wave research."
        ),
        language="Python",
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 0
    assert result.rejected_count == 1
    assert result.evaluated_candidates[0].admission.decision == "reject"
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "none"


def test_repository_admission_rejects_tutorial_style_repo_name() -> None:
    candidate = _build_candidate(
        item_id="github:repo:lab/lammps-tutorial-slides",
        title="lab/lammps-tutorial-slides",
        raw_text=(
            "lab/lammps-tutorial-slides\n"
            "Tutorial slides for using LAMMPS in a materials lab."
        ),
        language="Python",
        matched_channels=("code_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 0
    assert result.rejected_count == 1
    assert result.evaluated_candidates[0].admission.decision == "reject"
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "none"


def test_repository_admission_rejects_course_style_repo_name() -> None:
    candidate = _build_candidate(
        item_id="github:repo:school/quantum-course-notes",
        title="school/quantum-course-notes",
        raw_text=(
            "school/quantum-course-notes\n"
            "Course notes for an introduction to quantum chemistry."
        ),
        language="Jupyter Notebook",
        matched_channels=("repository_search",),
    )

    result = run_repository_admission((candidate,), mode="enforced")

    assert result.kept_count == 0
    assert result.rejected_count == 1
    assert result.evaluated_candidates[0].admission.decision == "reject"
    assert result.evaluated_candidates[0].admission.evidence.path_strength == "none"


def test_repository_admission_off_mode_shows_every_candidate() -> None:
    candidate = _build_candidate(
        item_id="github:repo:HeinrichHartmann/arxiv_meta",
        title="HeinrichHartmann/arxiv_meta",
        raw_text=(
            "HeinrichHartmann/arxiv_meta\n"
            "Arxiv metadata mirror."
        ),
        language="",
        matched_channels=("repository_search",),
    )

    result = run_repository_admission((candidate,), mode="off")

    assert result.kept_count == 1
    assert result.rejected_count == 0
    assert len(result.visible_candidates) == 1
    assert result.visible_candidates[0].admission.decision == "keep"
    assert result.visible_candidates[0].admission.evidence.path_strength == "none"


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
        item_id="github:repo:HeinrichHartmann/arxiv_meta",
        title="HeinrichHartmann/arxiv_meta",
        raw_text=(
            "HeinrichHartmann/arxiv_meta\n"
            "Arxiv metadata mirror."
        ),
        language="",
        matched_channels=("repository_search",),
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

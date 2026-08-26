"""Cheap repository admission rules."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.search.admission.models import AdmissionDecision, AdmissionEvidence
from app.services.search.retrieval.models import RepositoryCandidate

SOFTWARE_TERMS = (
    "package",
    "library",
    "toolkit",
    "tool",
    "plugin",
    "extension",
    "parser",
    "wrapper",
    "module",
    "sdk",
    "api",
    "workflow",
    "pipeline",
    "framework",
    "simulator",
    "simulation",
    "solver",
    "engine",
    "cli",
    "command line",
    "implementation",
    "integration",
    "validation",
    "validation suite",
    "pair style",
    "pair styles",
    "skill",
)

DATA_LIKE_TERMS = (
    "dataset",
    "data set",
    "metadata",
    "corpus",
    "archive",
    "dump",
    "mirror",
    "records",
)

PAPER_LIKE_TERMS = (
    "paper",
    "papers",
    "literature",
    "reading list",
    "bibliography",
    "survey",
)

COLLECTION_TERMS = (
    "awesome",
    "list",
    "collection",
    "catalog",
    "resources",
    "resource list",
    "index",
)

EDUCATION_TERMS = (
    "course",
    "lecture",
    "slides",
    "homework",
    "assignment",
    "notes",
    "tutorial",
    "tutorials",
)

STRONG_PATH_SEGMENT_HINTS = (
    "src/",
    "lib/",
    "app/",
    "cmd/",
    "bin/",
    "include/",
    "bindings/",
    "module/",
    "modules/",
    "python/",
    "fortran/",
    "lammps/",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "environment.yml",
    "environment.yaml",
    "project.toml",
    "manifest.toml",
    "cargo.toml",
    "package.json",
    "cmakelists.txt",
    "meson.build",
    "sconstruct",
    "makefile",
)

STRONG_PATH_EXTENSIONS = (
    ".py",
    ".pyx",
    ".pxd",
    ".pxi",
    ".r",
    ".jl",
    ".f90",
    ".f95",
    ".f03",
    ".f08",
    ".f",
    ".c",
    ".cc",
    ".hh",
    ".cpp",
    ".cxx",
    ".cu",
    ".cuh",
    ".h",
    ".hpp",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".m",
    ".mm",
    ".scala",
    ".sh",
    ".tcc",
)

DESCRIPTIVE_PATH_HINTS = (
    "readme",
    "docs/",
    "doc/",
    "examples/",
    "example/",
    "tutorial/",
    "tutorials/",
    "notebook/",
    "notebooks/",
)

DESCRIPTIVE_PATH_EXTENSIONS = (".md", ".rst", ".txt", ".ipynb")

WEAK_PATH_HINTS = (
    "tests/",
    "test/",
    "unittest/",
    "fixtures/",
    "fixture/",
    "mock/",
    "mocks/",
    "spec/",
    "specs/",
    "bench/",
)


@dataclass(frozen=True)
class CandidateFacts:
    """Normalized facts used by cheap admission rules."""

    has_code_search: bool
    matched_query_count: int
    hit_count: int
    has_language: bool
    language: str
    matched_channels: tuple[str, ...]
    software_term_hits: tuple[str, ...]
    data_like_term_hits: tuple[str, ...]
    paper_like_term_hits: tuple[str, ...]
    collection_term_hits: tuple[str, ...]
    education_term_hits: tuple[str, ...]
    path_strength: str
    evidence: AdmissionEvidence


def build_admission_decision(candidate: RepositoryCandidate) -> AdmissionDecision:
    """Return one conservative keep or reject decision."""

    facts = _build_candidate_facts(candidate)
    keep_reasons = _build_keep_reasons(facts)

    if facts.path_strength == "strong":
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(keep_reasons, "Matched a strong code path."),
            evidence=facts.evidence,
        )

    if facts.path_strength == "descriptive" and (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.matched_query_count >= 2
        or facts.hit_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(
                keep_reasons,
                "Matched a descriptive repository path.",
            ),
            evidence=facts.evidence,
        )

    if facts.has_code_search and (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.matched_query_count >= 2
        or facts.hit_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(keep_reasons, "Matched via code search."),
            evidence=facts.evidence,
        )

    if bool(facts.software_term_hits) and (
        facts.has_language or facts.matched_query_count >= 2 or facts.hit_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(
                keep_reasons,
                "Metadata looks like scientific software.",
            ),
            evidence=facts.evidence,
        )

    if facts.has_language and (facts.matched_query_count >= 2 or facts.hit_count >= 2):
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(
                keep_reasons,
                f"Declares {facts.language} as repository language.",
            ),
            evidence=facts.evidence,
        )

    if _is_clear_reject(facts):
        return AdmissionDecision(
            decision="reject",
            reasons=_build_reject_reasons(facts),
            evidence=facts.evidence,
        )

    return AdmissionDecision(
        decision="keep",
        reasons=("Kept by conservative default.",),
        evidence=facts.evidence,
    )


def _build_candidate_facts(candidate: RepositoryCandidate) -> CandidateFacts:
    signal = candidate.signal
    raw_text = signal.raw_text.casefold()
    title = signal.title.casefold()
    topics = " ".join(
        str(topic).casefold()
        for topic in signal.payload.get("topics", [])
        if isinstance(topic, str) and topic.strip()
    )
    language = str(signal.payload.get("language") or "").strip()
    combined_text = " ".join(part for part in (title, raw_text, topics) if part)
    matched_path = _read_matched_code_path(signal.raw_text)
    path_strength = _classify_path_strength(matched_path)
    software_term_hits = _find_term_hits(combined_text, SOFTWARE_TERMS)
    data_like_term_hits = _find_term_hits(combined_text, DATA_LIKE_TERMS)
    paper_like_term_hits = _find_term_hits(combined_text, PAPER_LIKE_TERMS)
    collection_term_hits = _find_term_hits(combined_text, COLLECTION_TERMS)
    education_term_hits = _find_term_hits(combined_text, EDUCATION_TERMS)
    matched_query_count = len(
        [query for query in candidate.provenance.matched_queries if query.strip()]
    )
    evidence = AdmissionEvidence(
        matched_channels=candidate.provenance.matched_channels,
        matched_query_count=matched_query_count,
        hit_count=candidate.provenance.hit_count,
        path_strength=path_strength,
        has_language=bool(language),
        software_term_hits=software_term_hits,
        data_like_term_hits=data_like_term_hits,
        paper_like_term_hits=paper_like_term_hits,
        collection_term_hits=collection_term_hits,
        education_term_hits=education_term_hits,
    )

    return CandidateFacts(
        has_code_search="code_search" in candidate.provenance.matched_channels,
        matched_query_count=matched_query_count,
        hit_count=candidate.provenance.hit_count,
        has_language=bool(language),
        language=language,
        matched_channels=candidate.provenance.matched_channels,
        software_term_hits=software_term_hits,
        data_like_term_hits=data_like_term_hits,
        paper_like_term_hits=paper_like_term_hits,
        collection_term_hits=collection_term_hits,
        education_term_hits=education_term_hits,
        path_strength=path_strength,
        evidence=evidence,
    )


def _build_keep_reasons(facts: CandidateFacts) -> tuple[str, ...]:
    reasons: list[str] = []
    if facts.has_code_search:
        reasons.append("Matched via code search.")
    if facts.path_strength == "strong":
        reasons.append("Matched a strong code path.")
    if facts.path_strength == "descriptive":
        reasons.append("Matched a descriptive repository path.")
    if facts.matched_query_count >= 2:
        reasons.append("Matched multiple discovery queries.")
    if facts.hit_count >= 2:
        reasons.append("Retrieved multiple times across the external search pool.")
    if facts.has_language:
        reasons.append(f"Declares {facts.language} as repository language.")
    if facts.software_term_hits:
        reasons.append("Metadata uses software-like terms.")
    return tuple(reasons)


def _is_clear_reject(facts: CandidateFacts) -> bool:
    if _has_strong_software_evidence(facts):
        return False

    has_negative_intent = bool(
        facts.data_like_term_hits
        or facts.paper_like_term_hits
        or facts.collection_term_hits
        or facts.education_term_hits
    )
    if not has_negative_intent:
        return False

    if bool(facts.data_like_term_hits) and not bool(facts.software_term_hits):
        return True

    if bool(facts.paper_like_term_hits) and bool(facts.collection_term_hits):
        return True

    if bool(facts.education_term_hits) and not (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.path_strength == "descriptive"
    ):
        return True

    if facts.path_strength == "weak" and not (
        facts.has_language or bool(facts.software_term_hits)
    ):
        return True

    return False


def _build_reject_reasons(facts: CandidateFacts) -> tuple[str, ...]:
    reasons: list[str] = []
    if facts.data_like_term_hits:
        reasons.append("Metadata looks like a data resource.")
    if facts.paper_like_term_hits and facts.collection_term_hits:
        reasons.append("Metadata looks like a paper or resource list.")
    elif facts.paper_like_term_hits:
        reasons.append("Metadata looks paper-focused without software evidence.")
    if facts.education_term_hits and not (facts.has_language or facts.software_term_hits):
        reasons.append("Metadata looks educational rather than software-focused.")
    if facts.path_strength == "weak":
        reasons.append("Matched only a weak repository path.")
    reasons.append("Only weak software evidence was available.")
    return tuple(dict.fromkeys(reasons))


def _read_matched_code_path(raw_text: str) -> str:
    for line in raw_text.splitlines():
        if line.startswith("Matched code path:"):
            return line.split(":", 1)[1].strip().casefold()
    return ""


def _find_term_hits(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def _classify_path_strength(path: str) -> str:
    if not path:
        return "none"
    if any(hint in path for hint in STRONG_PATH_SEGMENT_HINTS):
        return "strong"
    if path.endswith(STRONG_PATH_EXTENSIONS):
        return "strong"
    if any(hint in path for hint in DESCRIPTIVE_PATH_HINTS):
        return "descriptive"
    if path.endswith(DESCRIPTIVE_PATH_EXTENSIONS):
        return "descriptive"
    if any(hint in path for hint in WEAK_PATH_HINTS):
        return "weak"
    return "none"


def _has_strong_software_evidence(facts: CandidateFacts) -> bool:
    if facts.path_strength == "strong":
        return True
    if facts.has_code_search and (facts.has_language or bool(facts.software_term_hits)):
        return True
    if bool(facts.software_term_hits) and (
        facts.has_language or facts.matched_query_count >= 2 or facts.hit_count >= 2
    ):
        return True
    return False


def _has_soft_software_evidence(facts: CandidateFacts) -> bool:
    if facts.path_strength == "descriptive" and (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.matched_query_count >= 2
        or facts.hit_count >= 2
    ):
        return True
    if facts.has_language:
        return True
    if bool(facts.software_term_hits):
        return True
    return False


def _finalize_reasons(*reason_groups: tuple[str, ...] | str) -> tuple[str, ...]:
    ordered: list[str] = []
    for group in reason_groups:
        if isinstance(group, str):
            values = (group,)
        else:
            values = group
        for value in values:
            if value and value not in ordered:
                ordered.append(value)
    return tuple(ordered)

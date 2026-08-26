"""Cheap repository admission rules."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.search.admission.models import AdmissionDecision
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
)

NOISE_TERMS = (
    "dataset",
    "data set",
    "benchmark",
    "awesome",
    "paper",
    "papers",
    "literature",
    "reading list",
    "course",
    "lecture",
    "slides",
    "homework",
    "assignment",
    "notes",
)

CODE_PATH_SEGMENT_HINTS = (
    "src/",
    "lib/",
    "app/",
    "cmd/",
    "bin/",
    "tests/",
    "test/",
    "pyproject.toml",
    "setup.py",
    "cargo.toml",
    "package.json",
    "cmakelists.txt",
    "makefile",
)

CODE_PATH_EXTENSIONS = (
    ".py",
    ".pyx",
    ".ipynb",
    ".r",
    ".jl",
    ".f90",
    ".f",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
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
)

NON_CODE_PATH_HINTS = (
    "readme",
    "docs/",
    "doc/",
    "notes/",
    "paper/",
    "slides/",
)


@dataclass(frozen=True)
class CandidateFacts:
    """Normalized facts used by cheap admission rules."""

    has_code_search: bool
    matched_query_count: int
    hit_count: int
    has_language: bool
    language: str
    software_term_hits: tuple[str, ...]
    noise_term_hits: tuple[str, ...]
    has_code_like_path: bool
    has_non_code_path: bool


def build_admission_decision(candidate: RepositoryCandidate) -> AdmissionDecision:
    """Return one conservative keep or reject decision."""

    facts = _build_candidate_facts(candidate)
    keep_reasons = _build_keep_reasons(facts)

    if facts.has_code_like_path:
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(keep_reasons, "Matched a code-like file path."),
        )

    if facts.has_code_search and (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.matched_query_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(keep_reasons, "Matched via code search."),
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
        )

    if facts.has_language and (facts.matched_query_count >= 2 or facts.hit_count >= 2):
        return AdmissionDecision(
            decision="keep",
            reasons=_finalize_reasons(
                keep_reasons,
                f"Declares {facts.language} as repository language.",
            ),
        )

    if _is_clear_reject(facts):
        return AdmissionDecision(
            decision="reject",
            reasons=_build_reject_reasons(facts),
        )

    return AdmissionDecision(
        decision="keep",
        reasons=("Kept by conservative default.",),
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

    return CandidateFacts(
        has_code_search="code_search" in candidate.provenance.matched_channels,
        matched_query_count=len(
            [query for query in candidate.provenance.matched_queries if query.strip()]
        ),
        hit_count=candidate.provenance.hit_count,
        has_language=bool(language),
        language=language,
        software_term_hits=_find_term_hits(combined_text, SOFTWARE_TERMS),
        noise_term_hits=_find_term_hits(combined_text, NOISE_TERMS),
        has_code_like_path=_path_looks_like_code(matched_path),
        has_non_code_path=_path_has_any_hint(matched_path, NON_CODE_PATH_HINTS),
    )


def _build_keep_reasons(facts: CandidateFacts) -> tuple[str, ...]:
    reasons: list[str] = []
    if facts.has_code_search:
        reasons.append("Matched via code search.")
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
    if facts.has_code_like_path:
        return False
    if facts.has_code_search and not facts.has_non_code_path:
        return False
    if facts.has_language or facts.software_term_hits:
        return False
    if facts.matched_query_count >= 2 or facts.hit_count >= 2:
        return False
    if facts.has_non_code_path:
        return True
    return bool(facts.noise_term_hits)


def _build_reject_reasons(facts: CandidateFacts) -> tuple[str, ...]:
    reasons: list[str] = []
    if facts.has_non_code_path:
        reasons.append("Code search only matched a docs-like path.")
    if facts.noise_term_hits:
        reasons.append("Metadata looks non-software.")
    reasons.append("Only weak retrieval evidence was available.")
    return tuple(dict.fromkeys(reasons))


def _read_matched_code_path(raw_text: str) -> str:
    for line in raw_text.splitlines():
        if line.startswith("Matched code path:"):
            return line.split(":", 1)[1].strip().casefold()
    return ""


def _find_term_hits(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def _path_has_any_hint(path: str, hints: tuple[str, ...]) -> bool:
    return bool(path) and any(hint in path for hint in hints)


def _path_looks_like_code(path: str) -> bool:
    if not path:
        return False
    if any(hint in path for hint in CODE_PATH_SEGMENT_HINTS):
        return True
    return path.endswith(CODE_PATH_EXTENSIONS)


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

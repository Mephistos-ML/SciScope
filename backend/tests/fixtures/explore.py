"""Representative repository search results for transport and application tests."""

from app.models.ai import AiSearchPlan
from app.models.signal import Signal
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalMatchEvidence,
    RetrievalMatchLocation,
    RetrievedCandidates,
)


def build_explore_repository_signal(
    item_id: str,
    *,
    source: str = "github",
    query: str = "paramagnetic nmr",
) -> Signal:
    return Signal(
        source=source,
        kind="repository",
        item_id=item_id,
        title="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        published_at=None,
        raw_text=(
            "Mephistos-ML/paranmr\n"
            "Paramagnetic NMR software for susceptibility tensor fitting "
            "and PCS workflows."
        ),
        payload={
            "repo": "Mephistos-ML/paranmr",
            "query": query,
            "topics": ["paramagnetic-nmr", "pcs"],
            "language": "Python",
            "stars": 14,
        },
    )


def build_code_only_explore_repository_signal(
    item_id: str,
    *,
    source: str = "github",
    query: str = "LAMMPS Feynman-Hibbs",
) -> Signal:
    return Signal(
        source=source,
        kind="repository",
        item_id=item_id,
        title="thermotools/lammps_mie_fh",
        url="https://github.com/thermotools/lammps_mie_fh",
        published_at=None,
        raw_text=(
            "thermotools/lammps_mie_fh\n"
            "A LAMMPS package for Mie-FH simulations.\n"
            "Matched code path: src/pair_mie_fh.cpp"
        ),
        payload={
            "repo": "thermotools/lammps_mie_fh",
            "query": query,
            "topics": ["lammps", "molecular-simulation"],
            "language": "C++",
            "stars": 4,
        },
    )


def build_retrieved_candidates(
    *signals: Signal,
    source_statuses: tuple[dict[str, object], ...],
    successful_source_count: int,
    partial: bool = False,
    warnings: tuple[str, ...] = (),
    matched_channels: tuple[str, ...] = ("repository_search",),
    hit_count: int = 1,
    match_locations: tuple[RetrievalMatchLocation, ...] | None = None,
) -> RetrievedCandidates:
    return RetrievedCandidates(
        candidates=tuple(
            RepositoryCandidate(
                repository_id=signal.item_id,
                signal=signal,
                provenance=CandidateProvenance(
                    matched_queries=(str(signal.payload.get("query") or ""),),
                    matched_channels=matched_channels,
                    best_rank_by_channel={
                        channel_name: 1 for channel_name in matched_channels
                    },
                    hit_count=hit_count,
                    match_evidence=(
                        RetrievalMatchEvidence(
                            query=str(signal.payload.get("query") or ""),
                            location=(
                                (
                                    match_locations[index]
                                    if match_locations is not None
                                    else None
                                )
                                or (
                                    "code"
                                    if "Matched code path:" in signal.raw_text
                                    else "description"
                                )
                            ),
                            channel=matched_channels[0],
                            origin="provider",
                            retrieval_rank=1,
                        ),
                    ),
                ),
            )
            for index, signal in enumerate(signals)
        ),
        source_statuses=source_statuses,
        successful_source_count=successful_source_count,
        partial=partial,
        warnings=warnings,
    )


def build_ready_repository_ai_plan(*queries: str) -> AiSearchPlan:
    return AiSearchPlan(
        status="ready" if queries else "pending",
        queries=queries,
    )

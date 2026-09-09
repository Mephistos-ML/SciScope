"""External retrieval helpers for Explore search."""

from app.services.search.retrieval.merge import merge_repository_candidates
from app.services.search.retrieval.models import (
    CandidateProvenance, RepositoryCandidate, RetrievalMatchEvidence,
    RetrievedCandidates, RetrievalHit,
)
from app.services.search.retrieval.service import run_external_repository_retrieval

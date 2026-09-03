"""Diagnostic payload helpers for the internal Explore beta."""

from __future__ import annotations

from app.services.search.admission import AdmissionResult
from app.services.search.explore.evaluation import ExploreSearchEvaluation
from app.services.search.explore.items import build_repository_item
from app.services.search.ranking import RankingResult


def build_beta_items(evaluation: ExploreSearchEvaluation) -> list[dict[str, object]]:
    """Return every retrieved repository with internal diagnostics attached."""

    diagnostics = build_beta_diagnostics(
        admission=evaluation.admission,
        ranking=evaluation.ranking,
    )
    items: list[dict[str, object]] = []
    for ranked in evaluation.ranking.ranked_candidates:
        item = build_repository_item(ranked)
        item["beta"] = diagnostics[ranked.candidate.repository_id]
        items.append(item)
    return items


def build_beta_diagnostics(
    *,
    admission: AdmissionResult,
    ranking: RankingResult,
) -> dict[str, dict[str, object]]:
    """Build diagnostic decisions for every retrieved repository candidate."""

    admission_by_repository_id = {
        evaluated.candidate.repository_id: evaluated
        for evaluated in admission.evaluated_candidates
    }
    diagnostics: dict[str, dict[str, object]] = {}
    for ranked in ranking.ranked_candidates:
        evaluated = admission_by_repository_id[ranked.candidate.repository_id]
        diagnostics[ranked.candidate.repository_id] = {
            "decision": _build_beta_decision(
                admission_bucket=evaluated.admission.bucket,
                admission_kept=evaluated.admission.keep,
                score=ranked.score,
                relevance_cutoff=ranking.relevance_cutoff,
            ),
            "retrievalOrigin": _build_retrieval_origin(ranked.candidate.provenance.origins),
            "scoreBreakdown": {
                "queryCoverage": ranked.score_breakdown.query_coverage,
                "queryCoveragePoints": ranked.score_breakdown.query_coverage_points,
                "matchLocationQuality": ranked.score_breakdown.match_location_quality,
                "matchLocationPoints": ranked.score_breakdown.match_location_points,
                "evidenceDensity": ranked.score_breakdown.evidence_density,
                "evidenceDensityPoints": ranked.score_breakdown.evidence_density_points,
                "matchedQueryCount": ranked.features.matched_query_count,
                "queryCoverageAlignment": ranked.features.query_coverage_alignment,
                "totalQueryCount": ranked.features.total_query_count,
                "evidenceCount": ranked.features.evidence_count,
                "hitCount": ranked.features.hit_count,
            },
        }
    return diagnostics


def _build_retrieval_origin(origins: tuple[str, ...]) -> dict[str, str]:
    origin_set = set(origins)
    if "catalog" in origin_set and "provider" in origin_set:
        return {
            "kind": "catalog_and_provider",
            "label": "Loaded from SciScope catalog and refreshed by provider search",
        }
    if "catalog" in origin_set:
        return {
            "kind": "catalog",
            "label": "Loaded from SciScope catalog",
        }
    return {
        "kind": "provider",
        "label": "Retrieved from external provider search",
    }


def _build_beta_decision(
    *,
    admission_bucket: str,
    admission_kept: bool,
    score: float,
    relevance_cutoff: float,
) -> dict[str, object]:
    if admission_bucket == "repo_name_gate":
        return {
            "status": "gate_rejected",
            "admissionBucket": admission_bucket,
            "label": "Rejected by repository-name gate",
        }
    if not admission_kept:
        return {
            "status": "admission_rejected",
            "admissionBucket": admission_bucket,
            "label": "Rejected by admission",
        }
    if score < relevance_cutoff:
        return {
            "status": "below_cutoff",
            "admissionBucket": admission_bucket,
            "label": "Below relevance cutoff",
        }
    return {
        "status": "included",
        "admissionBucket": admission_bucket,
        "label": "Included in canonical results",
    }

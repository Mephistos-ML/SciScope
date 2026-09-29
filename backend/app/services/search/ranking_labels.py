"""Application service for human labels on immutable ranking snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.search_run import SearchRunRankingLabel
from app.storage.search_runs import (
    count_search_run_stages,
    get_search_run,
    list_search_run_ranking_repository_ids,
    upsert_search_run_ranking_labels,
)


def save_search_run_ranking_labels(
    *,
    user_id: str,
    run_id: str,
    labels: dict[str, int],
    database_url: str,
) -> dict[str, object]:
    """Save validated human judgments for the latest immutable run snapshot."""

    run = get_search_run(run_id, database_url=database_url)
    if run is None:
        raise ValueError("Search run was not found.")
    if run.owner_user_id != user_id:
        raise ValueError("This search run does not belong to the current user.")
    if run.status not in {"completed", "completed_partial"}:
        raise ValueError("Only completed search runs can be labelled.")
    if not labels or any(label not in {0, 1, 2} for label in labels.values()):
        raise ValueError("Labels must use only 0, 1, or 2.")

    stage_number = count_search_run_stages(run_id, database_url=database_url)
    if stage_number == 0:
        raise ValueError("Search run does not have an immutable ranking snapshot.")
    repository_ids = list_search_run_ranking_repository_ids(
        run_id,
        stage_number,
        database_url=database_url,
    )
    if not set(labels).issubset(repository_ids):
        raise ValueError("Labels must refer to candidates from the latest search snapshot.")

    now = datetime.now(UTC)
    upsert_search_run_ranking_labels(
        tuple(
            SearchRunRankingLabel(
                run_id=run_id,
                repository_id=repository_id,
                user_id=user_id,
                stage_number=stage_number,
                label=label,
                created_at=now,
                updated_at=now,
            )
            for repository_id, label in labels.items()
        ),
        database_url=database_url,
    )
    return {
        "runId": run_id,
        "stageNumber": stage_number,
        "labelledCount": len(labels),
    }

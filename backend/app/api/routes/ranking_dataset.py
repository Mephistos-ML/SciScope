"""Internal beta endpoint for manually labelled ranking data."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from app.services.auth import get_current_user
from app.services.features import has_feature
from app.services.ranking_dataset import save_ranking_dataset_run


def save_ranking_dataset_run_response(request: Request, payload: dict[str, object]) -> dict[str, object]:
    user = get_current_user(request, database_url=request.app.state.database_url)
    if user is None or not has_feature(user.email, "explore_beta"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal beta access is required.")
    search_job_id = str(payload.get("searchJobId") or "").strip()
    raw_labels = payload.get("labels")
    labels = {str(repository_id): value for repository_id, value in raw_labels.items() if isinstance(value, int) and not isinstance(value, bool)} if isinstance(raw_labels, dict) else {}
    try:
        return save_ranking_dataset_run(user_id=user.user_id, search_job_id=search_job_id, labels=labels, database_url=request.app.state.database_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This beta search was already saved as a dataset run.") from exc

"""Internal transport for labels on durable ranking snapshots."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services.auth.service import get_current_user
from app.services.features.access import has_feature
from app.services.search.ranking_labels import save_search_run_ranking_labels


def save_search_run_ranking_labels_response(
    request: Request,
    run_id: str,
    labels: dict[str, object],
) -> dict[str, object]:
    """Authorize and save human relevance labels for one completed run."""

    user = get_current_user(request, database_url=request.app.state.database_url)
    if user is None or not has_feature(user.email, "search_diagnostics"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Search diagnostics access is required.",
        )
    normalized_labels = {
        str(repository_id): value
        for repository_id, value in labels.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    try:
        return save_search_run_ranking_labels(
            user_id=user.user_id,
            run_id=run_id,
            labels=normalized_labels,
            database_url=request.app.state.database_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

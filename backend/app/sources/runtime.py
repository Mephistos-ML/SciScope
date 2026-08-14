"""Repository host orchestration for direct repository watches."""

from __future__ import annotations

import logging

from app.models.repository import Repository
from app.models.signal import Signal
from app.sources.common import RepositorySourceError
from app.sources.github.monitor import load_github_signals_for_subscription
from app.sources.github.state import sync_github_baseline
from app.sources.gitlab.monitor import load_gitlab_signals_for_subscription
from app.sources.gitlab.state import sync_gitlab_baseline

logger = logging.getLogger(__name__)


def sync_repository_baseline(subscription_id: str, repository: Repository) -> None:
    """Initialize monitoring baseline for one explicit repository watch."""

    for source_name, sync_baseline in (
        ("github", sync_github_baseline),
        ("gitlab", sync_gitlab_baseline),
    ):
        if repository.source != source_name:
            continue
        try:
            sync_baseline(subscription_id, repository)
        except RepositorySourceError as exc:
            logger.warning(
                "Repository baseline sync skipped for %s: %s",
                source_name,
                exc.public_message,
            )
        except Exception:
            logger.exception(
                "Repository baseline sync failed for %s.",
                source_name,
            )


def load_repository_signals(
    subscription_id: str,
    repository: Repository,
) -> list[Signal]:
    """Load live repository release signals for one explicit watch."""

    signals: list[Signal] = []
    for source_name, load_signals in (
        ("github", load_github_signals_for_subscription),
        ("gitlab", load_gitlab_signals_for_subscription),
    ):
        if repository.source != source_name:
            continue
        try:
            signals.extend(load_signals(subscription_id, repository))
        except RepositorySourceError as exc:
            logger.warning(
                "Repository monitoring source %s skipped: %s",
                source_name,
                exc.public_message,
            )
        except Exception:
            logger.exception(
                "Repository monitoring source %s failed unexpectedly.",
                source_name,
            )

    return signals

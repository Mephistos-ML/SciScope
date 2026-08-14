"""Low-level GitVerse HTTP client placeholder helpers."""

from __future__ import annotations

from app.__version__ import __version__
from app.sources.common import RepositorySourceError


GITVERSE_API_BASE = "https://api.gitverse.ru"


def build_user_agent() -> str:
    """Build the application user agent for outbound GitVerse requests."""

    return f"SciScope/{__version__}"


def fetch_json(url: str) -> object:
    """Raise until the GitVerse source is implemented."""

    del url
    raise RepositorySourceError(
        source="gitverse",
        status="disabled",
        public_message="GitVerse repository search is not implemented yet.",
    )

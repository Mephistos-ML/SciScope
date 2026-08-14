"""Low-level GitCode HTTP client placeholder helpers."""

from __future__ import annotations

from app.__version__ import __version__
from app.sources.common import RepositorySourceError


GITCODE_API_BASE = "https://api.gitcode.com"


def build_user_agent() -> str:
    """Build the application user agent for outbound GitCode requests."""

    return f"SciScope/{__version__}"


def fetch_json(url: str) -> object:
    """Raise until the GitCode source is implemented."""

    del url
    raise RepositorySourceError(
        source="gitcode",
        status="disabled",
        public_message="GitCode repository search is not implemented yet.",
    )

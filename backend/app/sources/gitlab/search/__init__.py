"""GitLab repository search lanes."""

from app.sources.gitlab.search.readme import (
    discover_repository_candidates_from_readme,
)
from app.sources.gitlab.search.repository import (
    discover_repository_candidates,
)

__all__ = [
    "discover_repository_candidates",
    "discover_repository_candidates_from_readme",
]

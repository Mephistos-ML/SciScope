# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Select concrete search implementations at application startup."""

import logging
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from urllib.parse import urlparse

from app import config
from app.composition.repositories import RepositoryAdapters
from app.composition.revision import resolve_backend_revision
from app.models.ai import AiPlannerIdentity
from app.integrations.ai.openai.planner import OpenAiSearchPlanner
from app.integrations.ai.openai.embeddings import OpenAiTextEmbedder
from app.services.ai.embeddings import EmbeddingProvider
from app.services.ai.planner import AiSearchPlanner
from app.services.ai.search_plans import build_bootstrap_ai_search_plan
from app.services.search.explore.dependencies import ExploreDependencies
from app.services.search.retrieval.models import RetrievalLane
from app.integrations.repositories.common.models import RepositoryDiscoveryBatch
from app.integrations.repositories.github.client import GitHubClient
from app.integrations.repositories.github.search.repository import discover_repository_candidates as github_repositories
from app.integrations.repositories.github.search.code import discover_repository_candidates_from_code as github_code
from app.integrations.repositories.gitlab.search.repository import discover_repository_candidates as gitlab_repositories
from app.integrations.repositories.gitlab.search.code import discover_repository_candidates_from_code as gitlab_code

logger = logging.getLogger(__name__)


def _github_code_with_coverage(
    queries: Sequence[str], *, client: GitHubClient, deadline_monotonic: float | None,
) -> RepositoryDiscoveryBatch:
    counts: list[int] = []
    signals = github_code(
        queries, client=client, deadline_monotonic=deadline_monotonic,
        per_query_limit=100, max_pages=3,
        report_result_count=counts.append,
    )
    return RepositoryDiscoveryBatch(tuple(signals), tuple(counts))


def build_explore_dependencies(*, repositories: RepositoryAdapters) -> ExploreDependencies:
    """Wire one process's planner and supported provider lanes from its config."""
    if config.AI_PLANNER_MODE == "openai":
        implementation = OpenAiSearchPlanner(
            api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL,
            timeout_seconds=config.OPENAI_TIMEOUT_SECONDS,
            model=config.OPENAI_MODEL, reasoning_effort=config.OPENAI_REASONING_EFFORT,
        )
        planner = AiSearchPlanner(
            build_search_plan=implementation.build_search_plan,
            identity=AiPlannerIdentity(
                mode="openai", model=implementation.model,
                reasoning_effort=implementation.reasoning_effort,
            ),
        )
    elif config.AI_PLANNER_MODE == "bootstrap":
        planner = AiSearchPlanner(
            build_search_plan=build_bootstrap_ai_search_plan,
            identity=AiPlannerIdentity(mode="bootstrap", model=None, reasoning_effort=None),
        )
    else:
        raise ValueError("Unsupported AI planner mode.")

    lanes = [
        RetrievalLane("github", "repository_search", partial(github_repositories, client=repositories.github)),
        RetrievalLane("github", "code_search", partial(_github_code_with_coverage, client=repositories.github)),
        RetrievalLane("gitlab", "repository_search", partial(gitlab_repositories, client=repositories.gitlab)),
    ]
    hostname = (urlparse(repositories.gitlab.base_url).hostname or "").casefold()
    if hostname not in {"gitlab.com", "www.gitlab.com"}:
        lanes.append(RetrievalLane("gitlab", "code_search", partial(gitlab_code, client=repositories.gitlab)))
    else:
        logger.info("GitLab global code-search lane is unavailable for configured host=%s", hostname)
    embeddings = build_embedding_provider() if config.SEMANTIC_CATALOG_ENABLED else None
    return ExploreDependencies(
        planner=planner, lanes=tuple(lanes), embeddings=embeddings,
        score_threshold=config.EXPLORE_SEARCH_LOG_MATCH_CUTOFF,
        backend_revision=resolve_backend_revision(
            config.APP_REVISION, repository_root=Path(__file__).resolve().parents[3],
        ),
    )


def build_embedding_provider() -> EmbeddingProvider:
    """Bind embedding configuration for search and the catalog backfill entrypoint."""
    embedder = OpenAiTextEmbedder(
        api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL,
        timeout_seconds=config.OPENAI_TIMEOUT_SECONDS,
        model=config.SEMANTIC_EMBEDDING_MODEL, dimensions=config.SEMANTIC_EMBEDDING_DIMENSIONS,
    )
    return EmbeddingProvider(model=embedder.model, embed=embedder)

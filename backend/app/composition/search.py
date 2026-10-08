"""Select concrete search implementations at application startup."""

import logging
from urllib.parse import urlparse

from app import config
from app.models.ai import AiPlannerIdentity
from app.integrations.ai.openai.planner import OpenAiSearchPlanner
from app.integrations.ai.openai.embeddings import OpenAiTextEmbedder
from app.services.ai.embeddings import EmbeddingProvider
from app.services.ai.planner import AiSearchPlanner
from app.services.ai.search_plans import build_bootstrap_ai_search_plan
from app.services.search.explore.dependencies import ExploreDependencies
from app.services.search.retrieval.models import RetrievalLane
from app.integrations.repositories.github.search.repository import discover_repository_candidates as github_repositories
from app.integrations.repositories.github.search.code import discover_repository_candidates_from_code as github_code
from app.integrations.repositories.gitlab.search.repository import discover_repository_candidates as gitlab_repositories
from app.integrations.repositories.gitlab.search.code import discover_repository_candidates_from_code as gitlab_code

logger = logging.getLogger(__name__)


def build_explore_dependencies() -> ExploreDependencies:
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
        RetrievalLane("github", "repository_search", github_repositories),
        RetrievalLane("github", "code_search", github_code),
        RetrievalLane("gitlab", "repository_search", gitlab_repositories),
    ]
    hostname = (urlparse(config.GITLAB_BASE_URL).hostname or "").casefold()
    if hostname not in {"gitlab.com", "www.gitlab.com"}:
        lanes.append(RetrievalLane("gitlab", "code_search", gitlab_code))
    else:
        logger.info("GitLab global code-search lane is unavailable for configured host=%s", hostname)
    embeddings = build_embedding_provider() if config.SEMANTIC_CATALOG_ENABLED else None
    return ExploreDependencies(planner=planner, lanes=tuple(lanes), embeddings=embeddings)


def build_embedding_provider() -> EmbeddingProvider:
    """Bind embedding configuration for search and the catalog backfill entrypoint."""
    embedder = OpenAiTextEmbedder(
        api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL,
        timeout_seconds=config.OPENAI_TIMEOUT_SECONDS,
        model=config.SEMANTIC_EMBEDDING_MODEL, dimensions=config.SEMANTIC_EMBEDDING_DIMENSIONS,
    )
    return EmbeddingProvider(model=embedder.model, embed=embedder)

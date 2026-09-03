"""Tests for repository persistence and direct repository watches."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.conftest import build_test_database_url, migrate_test_database
from app.models.repository import (
    Repository,
    RepositoryCheckpoint,
    RepositorySearchEvidence,
)
from app.storage.repositories import (
    find_catalog_repository_matches,
    get_repository_checkpoint,
    get_repository,
    list_repositories,
    list_repository_checkpoints,
    upsert_repositories,
    upsert_repository_search_evidence,
    upsert_repository_checkpoints,
)
from app.storage.subscriptions import create_subscription, list_subscription_watches_for_user


def test_upsert_repositories_persists_global_repositories(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "entities.sqlite3")
    migrate_test_database(database_url)

    upsert_repositories(
        [
            Repository(
                repository_id="github:repo:123",
                source="github",
                provider_repository_id="123",
                full_name="Mephistos-ML/paranmr",
                url="https://github.com/Mephistos-ML/paranmr",
                metadata={"stars": 12},
            )
        ],
        database_url=database_url,
    )

    repositories = list_repositories(source="github", database_url=database_url)

    assert len(repositories) == 1
    assert repositories[0].repository_id == "github:repo:123"
    assert repositories[0].full_name == "Mephistos-ML/paranmr"
    assert repositories[0].metadata["stars"] == 12


def test_create_subscription_returns_direct_repository_watch(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "entities.sqlite3")
    migrate_test_database(database_url)

    upsert_repositories(
        [
            Repository(
                repository_id="github:repo:123",
                source="github",
                provider_repository_id="123",
                full_name="Mephistos-ML/paranmr",
                url="https://github.com/Mephistos-ML/paranmr",
                metadata={"stars": 14},
            )
        ],
        database_url=database_url,
    )

    subscription = create_subscription(
        user_id="user_1",
        repository_id="github:repo:123",
        selected_query="paramagnetic nmr",
        database_url=database_url,
    )
    repository = get_repository(
        "github:repo:123",
        database_url=database_url,
    )
    watches = list_subscription_watches_for_user("user_1", database_url=database_url)

    assert subscription.repository_id == "github:repo:123"
    assert subscription.selected_query == "paramagnetic nmr"
    assert repository is not None
    assert len(watches) == 1
    assert watches[0].repository.full_name == "Mephistos-ML/paranmr"
    assert watches[0].selected_query == "paramagnetic nmr"


def test_catalog_search_uses_profile_and_durable_query_evidence(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "catalog.sqlite3")
    migrate_test_database(database_url)
    repository = Repository(
        repository_id="github:repo:123",
        source="github",
        provider_repository_id="123",
        full_name="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        description="Paramagnetic NMR fitting toolkit.",
        language="Python",
        topics=("paramagnetic-nmr", "pcs"),
    )
    upsert_repositories((repository,), database_url=database_url)
    upsert_repository_search_evidence(
        (
            RepositorySearchEvidence(
                repository_id=repository.repository_id,
                query_normalized="paramagnetic relaxation",
                channel="code_search",
                match_location="code",
                matched_path="paranmr/relaxation.py",
                matched_excerpt="Fit paramagnetic relaxation rates.",
                provider_rank=3,
            ),
        ),
        database_url=database_url,
    )

    pnmr_matches = find_catalog_repository_matches(
        ("paramagnetic nmr",),
        database_url=database_url,
    )
    relaxation_matches = find_catalog_repository_matches(
        ("relaxation",),
        database_url=database_url,
    )

    assert [match.repository.repository_id for match in pnmr_matches] == ["github:repo:123"]
    assert [match.repository.repository_id for match in relaxation_matches] == ["github:repo:123"]
    assert relaxation_matches[0].evidence[0].matched_path == "paranmr/relaxation.py"


def test_upsert_repository_checkpoints_persists_monitoring_cursor(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "entities.sqlite3")
    migrate_test_database(database_url)
    updated_at = datetime(2026, 7, 18, 9, 30, tzinfo=UTC)

    upsert_repository_checkpoints(
        [
            RepositoryCheckpoint(
                subscription_id="sub_pnmr",
                repository_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                checkpoint_key="latest_release_published_at",
                checkpoint_value="2026-07-18T09:00:00+00:00",
                updated_at=updated_at,
            )
        ],
        database_url=database_url,
    )

    checkpoints = list_repository_checkpoints(
        "sub_pnmr",
        "github:repo:Mephistos-ML/paranmr",
        database_url=database_url,
    )

    assert len(checkpoints) == 1
    assert checkpoints[0].checkpoint_key == "latest_release_published_at"
    assert checkpoints[0].checkpoint_value == "2026-07-18T09:00:00+00:00"
    assert checkpoints[0].updated_at == updated_at


def test_get_repository_checkpoint_returns_single_cursor(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "entities.sqlite3")
    migrate_test_database(database_url)
    updated_at = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)

    upsert_repository_checkpoints(
        [
            RepositoryCheckpoint(
                subscription_id="sub_pnmr",
                repository_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                checkpoint_key="latest_release_published_at",
                checkpoint_value="2026-07-18T10:30:00+00:00",
                updated_at=updated_at,
            )
        ],
        database_url=database_url,
    )

    checkpoint = get_repository_checkpoint(
        "sub_pnmr",
        "github:repo:Mephistos-ML/paranmr",
        "latest_release_published_at",
        database_url=database_url,
    )

    assert checkpoint is not None
    assert checkpoint.checkpoint_value == "2026-07-18T10:30:00+00:00"

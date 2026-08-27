"""Tests for repository-family shared models and factories."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.repository import Repository
from app.sources.common import (
    REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    RepositoryCandidate,
    RepositoryCommit,
    RepositoryRelease,
    build_repository_candidate_signal,
    build_repository_entity,
    build_repository_main_commit_checkpoint,
    build_repository_main_commit_signal,
    build_repository_release_checkpoint,
    build_repository_release_signal,
    read_repository_name,
)


def test_build_repository_candidate_signal_uses_shared_shape() -> None:
    candidate = RepositoryCandidate(
        source="github",
        full_name="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        query="paramagnetic nmr",
        description="Paramagnetic NMR tooling.",
        owner_login="Mephistos-ML",
        language="Python",
        stars=14,
        topics=("paramagnetic-nmr", "pcs"),
    )

    signal = build_repository_candidate_signal(candidate)

    assert signal.item_id == "github:repo:Mephistos-ML/paranmr"
    assert signal.payload["repo"] == "Mephistos-ML/paranmr"
    assert signal.payload["query"] == "paramagnetic nmr"
    assert "Paramagnetic NMR tooling." in signal.raw_text


def test_build_repository_entity_reuses_repository_metadata() -> None:
    signal = build_repository_candidate_signal(
        RepositoryCandidate(
            source="github",
            full_name="Mephistos-ML/paranmr",
            url="https://github.com/Mephistos-ML/paranmr",
            query="paramagnetic nmr",
            topics=("paramagnetic-nmr",),
            language="Python",
            stars=14,
        )
    )

    repository = build_repository_entity(signal)

    assert repository.full_name == "Mephistos-ML/paranmr"
    assert repository.metadata["repo"] == "Mephistos-ML/paranmr"


def test_build_repository_release_signal_and_checkpoint_use_shared_contract() -> None:
    release = RepositoryRelease(
        source="github",
        repo_full_name="Mephistos-ML/paranmr",
        release_id="12",
        title="v0.3.0",
        url="https://github.com/Mephistos-ML/paranmr/releases/tag/v0.3.0",
        published_at=datetime(2026, 7, 18, 11, 0, tzinfo=UTC),
        tag_name="v0.3.0",
        body="Adds PCS fitting improvements.",
    )
    repository = Repository(
        repository_id="github:repo:Mephistos-ML/paranmr",
        source="github",
        full_name="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )

    signal = build_repository_release_signal(release)
    checkpoint = build_repository_release_checkpoint(
        "sub_pnmr",
        repository,
        latest_published_at=release.published_at,
        fallback_started_after=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )

    assert signal.item_id == "Mephistos-ML/paranmr:release:12"
    assert signal.payload["repo"] == "Mephistos-ML/paranmr"
    assert checkpoint is not None
    assert checkpoint.subscription_id == "sub_pnmr"
    assert checkpoint.checkpoint_key == REPOSITORY_RELEASE_CHECKPOINT_KEY


def test_build_repository_main_commit_signal_and_checkpoint_use_shared_contract() -> None:
    commit = RepositoryCommit(
        source="github",
        repo_full_name="Mephistos-ML/paranmr",
        commit_sha="abcdef1234567890",
        title="Improve PCS tensor fitting",
        url="https://github.com/Mephistos-ML/paranmr/commit/abcdef1234567890",
        published_at=datetime(2026, 7, 18, 11, 0, tzinfo=UTC),
        branch="default",
        author_name="Ernest",
        body="Refine tensor optimization defaults.",
    )
    repository = Repository(
        repository_id="github:repo:Mephistos-ML/paranmr",
        source="github",
        full_name="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )

    signal = build_repository_main_commit_signal(commit)
    checkpoint = build_repository_main_commit_checkpoint(
        "sub_pnmr",
        repository,
        latest_published_at=commit.published_at,
        fallback_started_after=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )

    assert signal.item_id == "Mephistos-ML/paranmr:commit:abcdef1234567890"
    assert signal.payload["repo"] == "Mephistos-ML/paranmr"
    assert signal.payload["commit_sha"] == "abcdef1234567890"
    assert checkpoint is not None
    assert checkpoint.subscription_id == "sub_pnmr"
    assert checkpoint.checkpoint_key == REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY


def test_read_repository_name_uses_metadata_then_full_name() -> None:
    repository = Repository(
        repository_id="repo-1",
        source="gitlab",
        full_name="group/project",
        url="https://gitlab.com/group/project",
        metadata={},
    )

    assert read_repository_name(repository) == "group/project"

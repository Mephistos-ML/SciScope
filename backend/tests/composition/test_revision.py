# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Source identity uses actual disposable Git checkouts and explicit artifact metadata."""

import subprocess

import pytest

from app.composition.revision import resolve_backend_revision, source_revision


def test_clean_checkout_reports_full_sha(checkout):
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    assert source_revision(checkout, require_clean=True) == expected
    assert resolve_backend_revision("", repository_root=checkout) == expected


@pytest.mark.parametrize("filename", ["source.txt", "untracked.txt"])
def test_dirty_code_is_identified_and_cannot_be_deployed(checkout, filename):
    (checkout / filename).write_text("different source\n")
    assert source_revision(checkout).endswith("-dirty")
    with pytest.raises(RuntimeError, match="clean committed checkout"):
        source_revision(checkout, require_clean=True)


def test_explicit_image_sha_does_not_need_git_metadata(tmp_path):
    assert resolve_backend_revision("a" * 40, repository_root=tmp_path) == "a" * 40
    assert resolve_backend_revision("b" * 64, repository_root=tmp_path) == "b" * 64
    assert resolve_backend_revision("", repository_root=tmp_path) == "unavailable"


@pytest.mark.parametrize("value", ["unknown", "abc123", "a" * 40 + "-dirty"])
def test_invalid_artifact_revision_is_rejected(tmp_path, value):
    with pytest.raises(ValueError, match="full Git commit SHA"):
        resolve_backend_revision(value, repository_root=tmp_path)

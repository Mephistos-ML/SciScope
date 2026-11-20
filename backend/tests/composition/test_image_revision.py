# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Dashboard builds derive identity without exporting Git credentials or history."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "build_revision", ROOT / "backend/infra/build_revision.py"
)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


@pytest.mark.parametrize("head_kind", ["branch", "detached", "packed"])
def test_filtered_checkout_resolves_real_git_head(checkout, tmp_path_factory, head_kind):
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    if head_kind == "detached":
        subprocess.run(["git", "checkout", "--detach", "--quiet"], cwd=checkout, check=True)
    elif head_kind == "packed":
        subprocess.run(["git", "pack-refs", "--all"], cwd=checkout, check=True)
    context = tmp_path_factory.mktemp("filtered-context")
    metadata = context / ".git"
    metadata.mkdir()
    for name in ("HEAD", "packed-refs"):
        if (checkout / ".git" / name).exists():
            shutil.copyfile(checkout / ".git" / name, metadata / name)
    shutil.copytree(checkout / ".git/refs", metadata / "refs")
    assert not (metadata / "config").exists()
    assert not (metadata / "objects").exists()
    assert BUILDER.build_revision(context, "") == expected
    assert BUILDER.build_revision(context, expected) == expected
    with pytest.raises(ValueError, match="does not match"):
        BUILDER.build_revision(context, "0" * 40)


@pytest.mark.parametrize("revision", ["a" * 40, "b" * 64])
def test_source_archive_requires_explicit_valid_sha(tmp_path, revision):
    assert BUILDER.build_revision(tmp_path, revision) == revision
    for invalid in ("", "unknown", "abc123", revision + "-dirty"):
        with pytest.raises(ValueError, match="full source SHA"):
            BUILDER.build_revision(tmp_path, invalid)


@pytest.mark.parametrize("head", ["ref: ../../config", "ref: refs/heads/missing", "bad"])
def test_invalid_metadata_fails_build(tmp_path, head):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/HEAD").write_text(head)
    with pytest.raises(ValueError):
        BUILDER.build_revision(tmp_path, "")


@pytest.mark.parametrize(
    ("embedded", "configured", "expected_error"),
    [
        ("a" * 40, "", None),
        ("a" * 40, "a" * 40, None),
        ("b" * 64, "", None),
        ("a" * 40, "b" * 40, "must match"),
        ("", "a" * 40, "Image REVISION"),
        ("unknown", "", "Image REVISION"),
    ],
)
def test_all_python_entrypoints_read_image_identity(
    tmp_path, embedded, configured, expected_error
):
    # Import the actual configuration from a disposable image-shaped layout.
    app = tmp_path / "backend/app"
    app.mkdir(parents=True)
    shutil.copyfile(ROOT / "backend/app/config.py", app / "config.py")
    (app / "_image_revision.txt").write_text(embedded + "\n")
    env = dict(os.environ, APP_ENV="production", APP_REVISION=configured)
    result = subprocess.run(
        [sys.executable, "-c", f"import runpy; print(runpy.run_path({str(app / 'config.py')!r})['APP_REVISION'])"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    if expected_error:
        assert result.returncode != 0
        assert expected_error in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == embedded

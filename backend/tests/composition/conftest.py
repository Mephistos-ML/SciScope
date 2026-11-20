# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

import subprocess

import pytest


@pytest.fixture
def checkout(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, timeout=5)
    (tmp_path / "source.txt").write_text("committed source\n")
    subprocess.run(["git", "add", "source.txt"], cwd=tmp_path, check=True, timeout=5)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
        timeout=5,
    )
    return tmp_path

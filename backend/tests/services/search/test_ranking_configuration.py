# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Deployment configuration must not silently reuse the retired score scale."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


def _load_config(
    *,
    code="from app.config import EXPLORE_SEARCH_LOG_MATCH_CUTOFF; print(EXPLORE_SEARCH_LOG_MATCH_CUTOFF)",
    **settings,
):
    env = dict(os.environ)
    for key in (
        "EXPLORE_SEARCH_RELEVANCE_CUTOFF",
        "EXPLORE_SEARCH_LOG_MATCH_CUTOFF",
        "APP_REVISION",
    ):
        env.pop(key, None)
    env.update(settings)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])
    return subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_default_disables_additional_score_filtering():
    result = _load_config()
    assert result.returncode == 0, result.stderr
    assert float(result.stdout) == 0


def test_log_cutoff_is_not_bounded_to_one_hundred():
    result = _load_config(EXPLORE_SEARCH_LOG_MATCH_CUTOFF="101")
    assert result.returncode == 0, result.stderr
    assert float(result.stdout) == 101


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "-inf"])
def test_invalid_log_cutoff_fails_startup(value):
    result = _load_config(EXPLORE_SEARCH_LOG_MATCH_CUTOFF=value)
    assert result.returncode != 0
    assert "must be finite and nonnegative" in result.stderr


def test_old_scale_setting_requires_an_explicit_configuration_change():
    result = _load_config(EXPLORE_SEARCH_RELEVANCE_CUTOFF="50")
    assert result.returncode != 0
    assert "retired 0-100 scale" in result.stderr


def test_production_requires_an_explicit_full_source_sha():
    missing = _load_config(APP_ENV="production")
    assert missing.returncode != 0
    assert "APP_REVISION is required in production" in missing.stderr
    invalid = _load_config(APP_ENV="production", APP_REVISION="abc123")
    assert invalid.returncode != 0
    assert "full Git commit SHA" in invalid.stderr
    valid = _load_config(APP_ENV="production", APP_REVISION="a" * 40)
    assert valid.returncode == 0, valid.stderr

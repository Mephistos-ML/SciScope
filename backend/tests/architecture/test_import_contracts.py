"""Architecture gates reject real imports in isolated copies of the application."""

import os
from pathlib import Path
import shutil
import subprocess
import sysconfig

import pytest

from tests.conftest import BACKEND_ROOT, REPO_ROOT


@pytest.fixture
def isolated_application(tmp_path):
    shutil.copytree(BACKEND_ROOT / "app", tmp_path / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    return tmp_path


@pytest.mark.parametrize("package,statement", [
    ("models", "import fastapi"),
    ("services", "from ..database.records.auth import UserRecordModel"),
    ("services", "import app.integrations.repositories.github.client"),
    ("api/routes", "import app.storage.search_runs"),
    ("api", "import app.database.records.auth"),
    ("storage", "import app.services.search.explore.jobs"),
    ("integrations", "import app.api.auth"),
])
def test_forbidden_import_breaks_the_architecture_gate(isolated_application, package, statement):
    probe = isolated_application / "app" / package / "boundary_probe.py"
    probe.write_text(statement + "\n")
    result = subprocess.run(
        [str(Path(sysconfig.get_path("scripts")) / "lint-imports"), "--no-cache"],
        cwd=isolated_application,
        env={**os.environ, "PYTHONPATH": str(isolated_application)},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "BROKEN" in result.stdout
    assert "boundary_probe" in result.stdout


def test_new_dependency_cycle_breaks_the_architecture_gate(isolated_application):
    models = isolated_application / "app" / "models"
    (models / "cycle_left.py").write_text("from . import cycle_right\n")
    (models / "cycle_right.py").write_text("from . import cycle_left\n")
    result = subprocess.run(
        [str(Path(sysconfig.get_path("scripts")) / "lint-imports"), "--no-cache"],
        cwd=isolated_application,
        env={**os.environ, "PYTHONPATH": str(isolated_application)},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Application packages have no dependency cycles BROKEN" in result.stdout
    assert "cycle_left" in result.stdout or "cycle_right" in result.stdout

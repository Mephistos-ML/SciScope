# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata(
    root, *, backend="1.2.3", frontend="1.2.3", lock="1.2.3", lock_root="1.2.3"
):
    (root / "backend/app").mkdir(parents=True)
    (root / "frontend").mkdir()
    (root / "backend/app/__version__.py").write_text(f'__version__ = "{backend}"\n')
    (root / "frontend/package.json").write_text(json.dumps({"version": frontend}))
    (root / "frontend/package-lock.json").write_text(
        json.dumps({"version": lock, "packages": {"": {"version": lock_root}}})
    )


def test_release_versions_agree_in_the_real_checkout():
    assert (
        len(set(_script("check_release_versions").check_versions(ROOT).values())) == 1
    )


@pytest.mark.parametrize("field", ["backend", "frontend", "lock", "lock_root"])
def test_each_version_copy_is_checked(tmp_path, field):
    _metadata(tmp_path, **{field: "2.0.0"})
    with pytest.raises(ValueError, match="mismatch"):
        _script("check_release_versions").check_versions(tmp_path)


def test_release_writer_updates_all_version_copies(tmp_path, monkeypatch):
    _metadata(tmp_path)
    writer = _script("set_release_version")
    monkeypatch.setattr(
        writer, "BACKEND_VERSION_FILE", tmp_path / "backend/app/__version__.py"
    )
    monkeypatch.setattr(
        writer, "FRONTEND_PACKAGE_FILE", tmp_path / "frontend/package.json"
    )
    monkeypatch.setattr(
        writer, "FRONTEND_LOCK_FILE", tmp_path / "frontend/package-lock.json"
    )
    writer.update_backend_version("2.3.4")
    writer.update_frontend_package("2.3.4")
    writer.update_frontend_lock("2.3.4")
    assert set(_script("check_release_versions").check_versions(tmp_path).values()) == {
        "2.3.4"
    }


def test_generated_contracts_are_current_and_stale_edits_fail(tmp_path):
    for relative in (
        "backend/app/services/search/ranking/models.py",
        "backend/app/services/search/retrieval/models.py",
        "backend/app/models/scientific_domain.py",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    (tmp_path / "frontend/src/types").mkdir(parents=True)
    generator = _script("generate_search_contracts")
    generator.generate(ROOT, check=True)
    generator.generate(tmp_path, check=False)
    generator.generate(tmp_path, check=True)
    target = tmp_path / "frontend/src/types/searchContracts.generated.ts"
    target.write_text(target.read_text() + "// stale edit\n")
    with pytest.raises(ValueError, match="stale"):
        generator.generate(tmp_path, check=True)
    generator.generate(tmp_path, check=False)
    model = tmp_path / "backend/app/services/search/ranking/models.py"
    model.write_text(
        model.read_text().replace(
            "raw_hit_count: int", "provider_hit_count: int"
        )
    )
    with pytest.raises(ValueError, match="stale"):
        generator.generate(tmp_path, check=True)
    assert "provider_hit_count: number" in generator.render(tmp_path)


def test_deployment_command_embeds_a_clean_checkout_sha(checkout):
    # Reuse the real-Git behavior through an independent disposable fixture.
    command = _script("deploy_backend").deployment_command(checkout)
    from app.composition.revision import source_revision

    assert command == [
        "fly",
        "deploy",
        "--config",
        "fly.toml",
        "--build-arg",
        f"APP_REVISION={source_revision(checkout)}",
    ]

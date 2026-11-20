"""Publication must depend on the complete CI graph for its exact revision."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def workflow(name):
    # BaseLoader preserves GitHub's `on` key rather than treating it as YAML 1.1 true.
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_release_requires_reusable_quality_gates_without_a_bypass():
    release = workflow("release.yml")
    tests = workflow("test.yml")
    assert release["on"] == {"push": {"branches": ["main"]}}
    assert set(tests["on"]) == {"pull_request", "workflow_call"}
    checks = release["jobs"]["checks"]
    assert checks["uses"] == "./.github/workflows/test.yml"
    assert "if" not in checks
    required = {"backend-quality", "backend", "postgres", "frontend", "browser-journey"}
    assert required <= tests["jobs"].keys()
    for job in required:
        assert "if" not in tests["jobs"][job]
        assert tests["jobs"][job].get("continue-on-error", "false") == "false"
    publish = release["jobs"]["semantic-release"]
    assert publish["needs"] == "checks"
    assert "if" not in publish  # GitHub's default success() must gate the dependent job.


def test_publication_and_checks_use_the_event_revision():
    publish = workflow("release.yml")["jobs"]["semantic-release"]
    checkout = next(step for step in publish["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    guard = next(step for step in publish["steps"] if "TESTED_SHA" in step.get("env", {}))
    assert guard["env"]["TESTED_SHA"] == "${{ github.sha }}"
    assert 'git rev-parse HEAD' in guard["run"]
    assert 'git ls-remote origin refs/heads/main' in guard["run"]
    assert publish["steps"].index(guard) < next(
        i for i, step in enumerate(publish["steps"]) if "semantic-release" in step.get("run", "")
    )


def test_checks_do_not_receive_publication_permissions_or_all_secrets():
    release = workflow("release.yml")
    assert release["permissions"] == {"contents": "read"}
    assert release["jobs"]["checks"]["permissions"] == {"contents": "read"}
    assert release["jobs"]["checks"]["secrets"] == {"CODECOV_TOKEN": "${{ secrets.CODECOV_TOKEN }}"}
    assert workflow("test.yml")["permissions"] == {"contents": "read"}
    assert release["jobs"]["semantic-release"]["permissions"]["contents"] == "write"

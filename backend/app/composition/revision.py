# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Source revision resolution belongs to startup/build composition, not use cases."""

from pathlib import Path
import re
import subprocess


def source_revision(repository_root: Path, *, require_clean: bool = False) -> str:
    """Read an immutable Git revision, explicitly distinguishing local dirty code."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=normal"],
                cwd=repository_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            "Cannot determine source revision from this checkout"
        ) from exc
    if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha) is None:
        raise RuntimeError("Git returned an invalid source revision")
    if require_clean and dirty:
        raise RuntimeError("Deployment requires a clean committed checkout")
    return sha + ("-dirty" if dirty else "")


def resolve_backend_revision(configured_revision: str, *, repository_root: Path) -> str:
    """Use explicit artifact identity, or inspect an available development checkout."""
    if configured_revision:
        if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", configured_revision) is None:
            raise ValueError("APP_REVISION must be a full Git commit SHA")
        return configured_revision
    try:
        return source_revision(repository_root)
    except RuntimeError:
        # Source archives in development cannot truthfully claim a Git identity.
        # Production configuration rejects a missing revision before composition.
        return "unavailable"

# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Resolve image identity from an explicit SHA or filtered checkout metadata."""

import argparse
from pathlib import Path, PurePosixPath
import re


def build_revision(root: Path, revision: str) -> str:
    git_dir = root / ".git"
    checkout_revision = ""
    if git_dir.is_dir():
        head = (git_dir / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = head.removeprefix("ref: ")
            if (
                re.fullmatch(r"refs/[A-Za-z0-9_./-]+", ref) is None
                or ".." in PurePosixPath(ref).parts
            ):
                raise ValueError("Invalid Git HEAD reference")
            loose_ref = git_dir / ref
            if loose_ref.is_file():
                checkout_revision = loose_ref.read_text().strip()
            elif (git_dir / "packed-refs").is_file():
                for line in (git_dir / "packed-refs").read_text().splitlines():
                    fields = line.split()
                    if len(fields) == 2 and fields[1] == ref:
                        checkout_revision = fields[0]
                        break
        else:
            checkout_revision = head
        if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", checkout_revision) is None:
            raise ValueError("Cannot resolve a full source SHA from Git HEAD")
    if revision and checkout_revision and revision != checkout_revision:
        raise ValueError("APP_REVISION does not match the checkout HEAD")
    resolved = revision or checkout_revision
    if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", resolved) is None:
        raise ValueError("Supply APP_REVISION as a full source SHA or build from a Git checkout")
    return resolved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--revision", default="")
    args = parser.parse_args()
    try:
        print(build_revision(args.root, args.revision))
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

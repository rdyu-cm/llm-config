#!/usr/bin/env python3
"""Review changes to the ECC sources used by local scientific adaptations."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ITEMS = (
    "deep-research",
    "eval-harness",
    "unified-memory",
    "strategic-compact",
    "mle-workflow",
)


class ReviewError(RuntimeError):
    """A safe, actionable review failure."""


def run_git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git failure"
        raise ReviewError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def load_ecc_source(lock_path: Path) -> dict:
    try:
        with lock_path.open("rb") as handle:
            lock = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ReviewError(f"cannot read lock file {lock_path}: {error}") from error

    source = next(
        (item for item in lock.get("sources", []) if item.get("name") == "ecc"),
        None,
    )
    if source is None:
        raise ReviewError(f"ECC source is missing from {lock_path}")
    for field in ("repository", "commit", "items"):
        if field not in source:
            raise ReviewError(f"ECC source is missing required field {field!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
        raise ReviewError("ECC source commit must be a full lowercase 40-character SHA")
    if tuple(source["items"]) != EXPECTED_ITEMS:
        raise ReviewError("ECC source items differ from the five reviewed scientific inputs")
    return source


def resolve_head(repository: str) -> str:
    output = run_git("ls-remote", repository, "HEAD")
    fields = output.split()
    if not fields or not re.fullmatch(r"[0-9a-f]{40}", fields[0]):
        raise ReviewError(f"could not resolve ECC HEAD from {repository}")
    return fields[0]


def fetch_ref(repo: Path, repository: str, revision: str, ref: str) -> None:
    run_git("fetch", "--quiet", "--depth=1", repository, revision, cwd=repo)
    run_git("update-ref", ref, "FETCH_HEAD", cwd=repo)


def review(lock_path: Path, candidate: str | None) -> int:
    source = load_ecc_source(lock_path)
    repository = source["repository"]
    pinned = source["commit"]
    candidate = candidate or resolve_head(repository)
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        raise ReviewError("candidate must resolve to a full lowercase 40-character SHA")

    paths = [f"skills/{item}" for item in EXPECTED_ITEMS]
    with tempfile.TemporaryDirectory(prefix="ecc-update-review-") as directory:
        repo = Path(directory)
        run_git("init", "--quiet", cwd=repo)
        fetch_ref(repo, repository, pinned, "refs/ecc/pinned")
        if candidate == pinned:
            run_git("update-ref", "refs/ecc/candidate", "refs/ecc/pinned", cwd=repo)
        else:
            fetch_ref(repo, repository, candidate, "refs/ecc/candidate")
        changes = run_git(
            "diff",
            "--name-status",
            "--find-renames",
            "refs/ecc/pinned",
            "refs/ecc/candidate",
            "--",
            *paths,
            cwd=repo,
        ).rstrip()

    print(f"ECC pinned:    {pinned}")
    print(f"ECC candidate: {candidate}")
    if changes:
        print("Changes in adopted ECC source paths:")
        print(changes)
    else:
        print("No changes in the five adopted ECC source paths.")
    print("This review does not modify skills, the lock file, or either checkout.")
    print("Next: inspect the upstream diff, adapt relevant changes locally, run verification, then update the pin manually.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "sources.lock.toml")
    parser.add_argument("--candidate", help="full upstream commit; defaults to repository HEAD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return review(args.lock, args.candidate)
    except ReviewError as error:
        print(f"ECC update review failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

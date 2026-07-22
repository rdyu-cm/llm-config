#!/usr/bin/env python3
"""Report a cached, best-effort gstack upstream update notice."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import tomllib
from pathlib import Path


CACHE_VERSION = 1
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
HEAD_PATTERN = re.compile(r"[0-9a-f]{40}")
CACHED_HEAD_PATTERN = re.compile(r"[0-9a-f]{12,40}")


def cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "codex-config" / "gstack-update.json"


def gstack_source(lock_path: Path) -> tuple[str, str]:
    with lock_path.open("rb") as handle:
        sources = tomllib.load(handle).get("sources", [])
    source = next((item for item in sources if item.get("name") == "gstack"), None)
    if not isinstance(source, dict):
        raise ValueError("sources.lock.toml is missing gstack")
    repository = source.get("repository")
    pinned = source.get("commit")
    if not isinstance(repository, str) or not isinstance(pinned, str) or not HEAD_PATTERN.fullmatch(pinned):
        raise ValueError("invalid gstack source lock")
    return repository, pinned


def cached_head(cache: Path) -> str | None:
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    checked_at = data.get("checked_at")
    head = data.get("head")
    if not isinstance(checked_at, (int, float)) or not isinstance(head, str):
        return None
    if time.time() - checked_at > CACHE_MAX_AGE_SECONDS or not CACHED_HEAD_PATTERN.fullmatch(head):
        return None
    return head


def remote_gstack_head(repository: str) -> str | None:
    result = subprocess.run(
        ["git", "ls-remote", repository, "HEAD"],
        timeout=2,
        check=True,
        capture_output=True,
        text=True,
    )
    head = result.stdout.split(maxsplit=1)[0] if result.stdout.split() else ""
    return head if HEAD_PATTERN.fullmatch(head) else None


def write_cache(cache: Path, pinned: str, head: str) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_name(f".{cache.name}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(
            {"version": CACHE_VERSION, "checked_at": time.time(), "pinned": pinned, "head": head},
            handle,
        )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, cache)
    os.chmod(cache, 0o600)


def notice(pinned: str, head: str) -> str | None:
    if head == pinned:
        return None
    return f"update  gstack: {pinned[:12]} -> {head[:12]}\n        run ./scripts/update-gstack.sh"


def check_update(lock_path: Path, cache_path: Path, force: bool, remote_head: str | None = None) -> str | None:
    """Return an informational update notice, without surfacing lookup or cache failures."""
    try:
        repository, pinned = gstack_source(lock_path)
        head = None if force else cached_head(cache_path)
        if head is None:
            head = remote_head if remote_head is not None else remote_gstack_head(repository)
            if not isinstance(head, str) or not HEAD_PATTERN.fullmatch(head):
                return None
            write_cache(cache_path, pinned, head)
        return notice(pinned, head)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    if arguments.notify:
        result = check_update(
            Path(__file__).resolve().parents[1] / "sources.lock.toml",
            cache_path(),
            arguments.force,
            os.environ.get("GSTACK_REMOTE_HEAD"),
        )
        if result:
            print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

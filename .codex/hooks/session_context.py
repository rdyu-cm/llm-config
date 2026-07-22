#!/usr/bin/env python3
"""Inject one compact reminder without performing any external work."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from gstack_updates import cache_path, check_update


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        pass

    context = (
        "Portable Codex config is active. Keep changes surgical and verify before completion. "
        "Codebase Memory is configured in the portable config and should be used when its tools are surfaced; "
        "otherwise use rg."
    )
    if os.environ.get("CODEX_CONFIG_UPDATE_CHECK", "1") != "0":
        try:
            remote_head = os.environ.get("GSTACK_REMOTE_HEAD")
            update_notice = check_update(
                ROOT / "sources.lock.toml", cache_path(), remote_head is not None, remote_head
            )
            if update_notice:
                context = f"{context}\n\n{update_notice}"
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

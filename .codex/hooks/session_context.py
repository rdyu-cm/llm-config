#!/usr/bin/env python3
"""Inject one compact reminder without performing any external work."""

from __future__ import annotations

import json
import shutil
import sys


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        pass

    graph = "available" if shutil.which("codebase-memory-mcp") else "configured through the full profile"
    context = (
        "Portable Codex config is active. Keep changes surgical and verify before completion. "
        f"Codebase Memory is {graph}; prefer graph discovery when its tools are surfaced, otherwise use rg."
    )
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


#!/usr/bin/env python3
"""Inject one compact reminder without performing any external work."""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        pass

    context = (
        "Portable Claude Code config is active. Keep changes surgical and verify before completion. "
        "Codebase Memory is configured in the portable config and should be used when its tools are surfaced; "
        "otherwise use rg."
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

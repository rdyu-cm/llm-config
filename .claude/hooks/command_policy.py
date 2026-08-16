#!/usr/bin/env python3
"""Block a small set of unambiguously destructive shell commands."""

import json
import re
import sys


RULES = (
    (re.compile(r"(?:^|[;&|]\s*)rm\s+-[^\n]*[rf][^\n]*\s+(?:/|~|\$HOME)(?:/)?(?:\s|$)"), "recursive deletion of a home or filesystem root"),
    (re.compile(r"(?:^|[;&|]\s*)(?:sudo\s+)?mkfs(?:\.[a-z0-9]+)?\b"), "filesystem formatting"),
    (re.compile(r"\bdd\b[^\n]*\bof=/dev/(?:sd[a-z]|nvme\d+n\d+|disk\d+)\b"), "raw write to a storage device"),
    (re.compile(r"(?:^|[;&|]\s*)(?:sudo\s+)?(?:shutdown|reboot|poweroff)\b"), "machine shutdown or reboot"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), "fork bomb"),
)


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Portable Claude Code policy blocked {reason}.",
                }
            }
        )
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if not isinstance(command, str):
        return 0

    for pattern, reason in RULES:
        if pattern.search(command):
            deny(reason)
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


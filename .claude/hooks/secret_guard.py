#!/usr/bin/env python3
"""Reject writes that appear to add secret files or credential material."""

from __future__ import annotations

import json
import re
import sys


SENSITIVE_PATH = re.compile(
    r"(?:^|/)(?:\.env|auth\.json|credentials\.json|service[-_]?account[^/]*\.json|"
    r"id_rsa|id_ed25519|[^/]+\.(?:pem|p12|pfx))$",
    re.IGNORECASE,
)
SAFE_ENV_SUFFIXES = (".example", ".sample", ".template")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


def block(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0
    path = tool_input.get("file_path", "")
    if isinstance(path, str) and path:
        normalized = path.strip().replace("\\", "/")
        if not (
            normalized.lower().startswith(".env")
            and normalized.lower().endswith(SAFE_ENV_SUFFIXES)
        ) and SENSITIVE_PATH.search(normalized):
            block(f"Portable Claude Code policy blocked writing likely secret file: {normalized}")
            return 0
    content = "\n".join(
        value
        for key in ("content", "new_string", "command")
        if isinstance((value := tool_input.get(key, "")), str)
    )
    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            block("Portable Claude Code policy blocked text resembling a credential or private key.")
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

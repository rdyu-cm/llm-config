#!/usr/bin/env python3
"""Reject patches that appear to add secret files or credential material."""

from __future__ import annotations

import json
import re
import sys


PATH_LINE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.MULTILINE)
SENSITIVE_PATH = re.compile(
    r"(?:^|/)(?:\.env|auth\.json|credentials\.json|service[-_]?account[^/]*\.json|id_rsa|id_ed25519|[^/]+\.(?:pem|p12|pfx))$",
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

    patch = payload.get("tool_input", {}).get("command", "")
    if not isinstance(patch, str):
        return 0

    for path in PATH_LINE.findall(patch):
        normalized = path.strip().replace("\\", "/")
        if normalized.lower().startswith(".env") and normalized.lower().endswith(SAFE_ENV_SUFFIXES):
            continue
        if SENSITIVE_PATH.search(normalized):
            block(f"Portable Codex policy blocked writing likely secret file: {normalized}")
            return 0

    added_text = "\n".join(
        line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    for pattern in SECRET_PATTERNS:
        if pattern.search(added_text):
            block("Portable Codex policy blocked text resembling a credential or private key.")
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


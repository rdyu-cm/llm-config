#!/usr/bin/env python3
"""Small stdlib-only contract tests for the portable Codex hooks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".codex" / "hooks"


def run_hook(
    name: str, command: str, tool_name: str = "Bash", environment: dict[str, str] | None = None
) -> dict | None:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    result = subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        env={**os.environ, **(environment or {})},
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


class CommandPolicyTests(unittest.TestCase):
    def test_allows_scoped_cleanup(self) -> None:
        self.assertIsNone(run_hook("command_policy.py", "rm -rf build"))

    def test_blocks_root_cleanup(self) -> None:
        output = run_hook("command_policy.py", "rm -rf /")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_blocks_device_write(self) -> None:
        output = run_hook("command_policy.py", "dd if=image.iso of=/dev/sda")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")


class SecretGuardTests(unittest.TestCase):
    def test_allows_env_example(self) -> None:
        patch = "*** Begin Patch\n*** Add File: .env.example\n+TOKEN=\n*** End Patch"
        self.assertIsNone(run_hook("secret_guard.py", patch, "apply_patch"))

    def test_blocks_env_file(self) -> None:
        patch = "*** Begin Patch\n*** Add File: .env\n+TOKEN=value\n*** End Patch"
        output = run_hook("secret_guard.py", patch, "apply_patch")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_blocks_private_key(self) -> None:
        patch = "*** Begin Patch\n*** Add File: key.txt\n+-----BEGIN PRIVATE KEY-----\n*** End Patch"
        output = run_hook("secret_guard.py", patch, "apply_patch")
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")


class SessionContextTests(unittest.TestCase):
    def test_describes_codebase_memory_without_profile_specific_inference(self) -> None:
        output = run_hook("session_context.py", "")
        context = output["hookSpecificOutput"]["additionalContext"]

        self.assertIn(
            "Codebase Memory is configured in the portable config and should be used when its tools are surfaced; "
            "otherwise use rg.",
            context,
        )
        self.assertNotIn("configured through the full profile", context)


if __name__ == "__main__":
    unittest.main()

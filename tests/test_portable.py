from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values = {}
    for line in lines[1 : lines.index("---", 1)]:
        if ": " in line:
            key, value = line.split(": ", 1)
            values[key] = value
    return values


def run_hook(name: str, payload: dict) -> dict | None:
    result = subprocess.run(
        [sys.executable, str(ROOT / ".claude/hooks" / name)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


class ConfigurationTests(unittest.TestCase):
    def test_json_configuration_and_profiles(self) -> None:
        for path in (ROOT / ".claude/settings.json", ROOT / ".claude/mcp.json"):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)
        profiles = list((ROOT / "profiles").glob("*.mcp.json"))
        self.assertEqual(len(profiles), 4)
        for path in profiles:
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_required_hooks_are_configured(self) -> None:
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(set(settings["hooks"]), {"SessionStart", "PreToolUse"})

    def test_models_are_routed_to_exact_named_roles(self) -> None:
        agents = {
            data["name"]: data
            for path in (ROOT / ".claude/agents").glob("*.md")
            if (data := frontmatter(path))
        }
        fable = {name for name, data in agents.items() if data["model"] == "claude-fable-5"}
        self.assertEqual(
            fable,
            {"planner", "implementer-deep", "reviewer-deep", "security-reviewer"},
        )
        self.assertTrue(
            all(data["model"] == "claude-opus-5" for name, data in agents.items() if name not in fable)
        )


class HookTests(unittest.TestCase):
    def test_command_policy_blocks_root_but_allows_scoped_cleanup(self) -> None:
        blocked = run_hook(
            "command_policy.py", {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}
        )
        allowed = run_hook(
            "command_policy.py", {"tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(allowed)

    def test_secret_guard_understands_claude_write_payloads(self) -> None:
        blocked = run_hook(
            "secret_guard.py",
            {"tool_name": "Write", "tool_input": {"file_path": ".env", "content": "TOKEN=x"}},
        )
        allowed = run_hook(
            "secret_guard.py",
            {"tool_name": "Write", "tool_input": {"file_path": ".env.example", "content": "TOKEN="}},
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(allowed)

    def test_secret_guard_blocks_private_keys_in_edits(self) -> None:
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        blocked = run_hook(
            "secret_guard.py",
            {"tool_name": "Edit", "tool_input": {"file_path": "note.txt", "new_string": marker}},
        )
        self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")


class MergeAndBootstrapTests(unittest.TestCase):
    def test_portable_settings_win_recursive_merge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            local = root / "local.json"
            output = root / "output.json"
            base.write_text('{"model":"claude-opus-5","permissions":{"defaultMode":"default"}}')
            local.write_text('{"model":"local","permissions":{"extra":true},"theme":"dark"}')
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/sync_config.py"),
                    "--base",
                    str(base),
                    "--local",
                    str(local),
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            merged = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(merged["model"], "claude-opus-5")
            self.assertEqual(merged["permissions"], {"defaultMode": "default", "extra": True})
            self.assertEqual(merged["theme"], "dark")

    def test_bootstrap_defaults_to_non_mutating_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/bootstrap.sh")],
                env={**os.environ, "HOME": str(home), "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("dry-run", result.stdout.lower())
            self.assertFalse((home / ".claude").exists())

    def test_apply_preflights_missing_claude_before_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            bin_dir = root / "bin"
            home.mkdir()
            bin_dir.mkdir()
            for name, target in (("python3", sys.executable), ("bash", "/bin/bash")):
                (bin_dir / name).symlink_to(target)
            result = subprocess.run(
                ["/bin/bash", str(ROOT / "scripts/bootstrap.sh"), "--apply"],
                env={"HOME": str(home), "PATH": str(bin_dir), "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Claude Code CLI is required", result.stderr)
            self.assertFalse((home / ".claude").exists())


if __name__ == "__main__":
    unittest.main()

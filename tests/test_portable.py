from __future__ import annotations

import json
import os
import shutil
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

    def test_sandbox_confines_commands_without_becoming_a_hard_gate(self) -> None:
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        sandbox = settings["sandbox"]
        self.assertTrue(sandbox["enabled"])
        # Unsupported platforms and missing bubblewrap must degrade to a warning,
        # and the model must keep an escape hatch, or portability regresses.
        self.assertFalse(sandbox["failIfUnavailable"])
        self.assertTrue(sandbox["allowUnsandboxedCommands"])
        protected = {entry["path"] for entry in sandbox["credentials"]["files"]}
        self.assertIn("~/.claude/.credentials.json", protected)
        self.assertIn("~/.ssh", protected)
        self.assertTrue(all(entry["mode"] == "deny" for entry in sandbox["credentials"]["files"]))
        self.assertTrue(
            all(
                entry["mode"] in {"deny", "mask"}
                for entry in sandbox["credentials"]["envVars"]
            )
        )
        self.assertIn("169.254.169.254", sandbox["network"]["deniedDomains"])

    def test_models_are_routed_to_exact_named_roles(self) -> None:
        agents = {
            data["name"]: data
            for path in (ROOT / ".claude/agents").glob("*.md")
            if (data := frontmatter(path))
        }
        fable = {name for name, data in agents.items() if data["model"] == "claude-fable-5"}
        self.assertEqual(
            fable,
            {"Plan", "planner", "implementer-deep", "reviewer-deep", "security-reviewer"},
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

    def test_merge_keeps_unrelated_local_hooks_alive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            local = root / "local.json"
            output = root / "output.json"
            base.write_text(
                json.dumps({"hooks": {"SessionStart": [{"matcher": "startup", "hooks": ["p"]}]}})
            )
            local.write_text(
                json.dumps({"hooks": {"SessionStart": [{"hooks": ["agent-session"]}]}})
            )
            self.run_sync(base, local, output)
            starts = json.loads(output.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
            self.assertEqual(len(starts), 2)
            self.assertIn({"hooks": ["agent-session"]}, starts)
            # A second pass must not accumulate duplicates.
            self.run_sync(base, local, output)
            self.assertEqual(
                len(json.loads(output.read_text(encoding="utf-8"))["hooks"]["SessionStart"]), 2
            )

    def test_toml_and_json_share_one_merge(self) -> None:
        # Codex stores config as TOML and Claude Code as JSON. Only load and
        # render may differ; the merge semantics must be the same or the two
        # providers drift apart again.
        import tomllib

        for suffix, base_text, local_text in (
            (".toml", 'a = "portable"\nb = [2]\n', 'a = "local"\nb = [1]\nkeep = true\n'),
            (".json", '{"a":"portable","b":[2]}', '{"a":"local","b":[1],"keep":true}'),
        ):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                base = root / f"base{suffix}"
                local = root / f"local{suffix}"
                output = root / f"out{suffix}"
                base.write_text(base_text)
                local.write_text(local_text)
                self.run_sync(base, local, output)
                if suffix == ".toml":
                    with output.open("rb") as handle:
                        merged = tomllib.load(handle)
                else:
                    merged = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(merged["a"], "portable")
                self.assertEqual(merged["b"], [1, 2])
                self.assertTrue(merged["keep"])

    def test_carry_folds_unmanaged_settings_into_the_local_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            local = root / "local.json"
            carry = root / "carry.json"
            output = root / "output.json"
            base.write_text('{"model":"claude-opus-5"}')
            local.write_text('{"theme":"dark"}')
            carry.write_text('{"statusLine":{"type":"command"},"theme":"light"}')
            self.run_sync(base, local, output, carry=carry)
            overlay = json.loads(local.read_text(encoding="utf-8"))
            merged = json.loads(output.read_text(encoding="utf-8"))
            # The unmanaged statusLine survives; the overlay wins where both set a key.
            self.assertEqual(overlay["statusLine"], {"type": "command"})
            self.assertEqual(overlay["theme"], "dark")
            self.assertEqual(merged["model"], "claude-opus-5")
            self.assertEqual(merged["statusLine"], {"type": "command"})

    def run_sync(self, base: Path, local: Path, output: Path, carry: Path | None = None) -> None:
        command = [
            sys.executable,
            str(ROOT / "scripts/sync_config.py"),
            "--base",
            str(base),
            "--local",
            str(local),
            "--output",
            str(output),
        ]
        if carry is not None:
            command += ["--carry", str(carry)]
        subprocess.run(command, check=True, capture_output=True, text=True)

    def test_bootstrap_links_skills_individually_beside_foreign_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            foreign = home / ".claude/skills/foreign-skill"
            foreign.mkdir(parents=True)
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/bootstrap.sh")],
                env={**os.environ, "HOME": str(home), "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )
            # A pre-existing neighbour must not be a conflict.
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("/.claude/skills/writing-plans ->", result.stdout)
            self.assertNotIn("foreign-skill", result.stdout)
            self.assertTrue(foreign.exists())

    def test_install_refuses_an_interpreter_older_than_the_validator_needs(self) -> None:
        # A bare `python3` probe passes on the 3.9 interpreters that ship with
        # several long-term-support distributions, then fails later on tomllib.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "python3").write_text(
                "#!/bin/sh\n"
                'case "$1" in --version) echo "Python 3.9.18"; exit 0;; esac\n'
                'exec /usr/bin/env python3.9 "$@" 2>/dev/null || exit 1\n'
            )
            (bin_dir / "python3").chmod(0o755)
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/install.sh"), "--dry-run"],
                env={"HOME": str(root / "home"), "PATH": f"{bin_dir}:/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Python 3.11 or newer is required", result.stderr)
            self.assertFalse((root / "home/.claude").exists())

    def test_install_verification_counts_through_symlinks(self) -> None:
        # The installed entries are symlinks, so a verification step that does
        # not follow them counts zero and would report a broken install as fine.
        source = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertIn("find -L", source)
        self.assertNotIn("$(find \"$HOME", source)

    def bootstrap(self, home: Path, *args: str, stubs: Path | None = None) -> subprocess.CompletedProcess:
        path = f"{stubs}:{os.environ['PATH']}" if stubs else os.environ["PATH"]
        return subprocess.run(
            ["bash", str(ROOT / "scripts/bootstrap.sh"), *args],
            env={**os.environ, "HOME": str(home), "PATH": path, "PYTHON": sys.executable},
            capture_output=True,
            text=True,
        )

    def stub_clis(self, root: Path) -> Path:
        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        for name in ("codex", "claude"):
            (bin_dir / name).write_text("#!/bin/sh\nexit 0\n")
            (bin_dir / name).chmod(0o755)
        return bin_dir

    def test_each_target_installs_only_its_own_provider(self) -> None:
        expected = {
            "codex": (".codex/AGENTS.md", ".codex/config.toml", ".codex/hooks.json", ".agents/skills"),
            "claude": (".claude/CLAUDE.md", ".claude/settings.json", ".claude/skills"),
        }
        other = {"codex": ".claude", "claude": ".codex"}
        for target in ("codex", "claude"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "home"
                home.mkdir()
                result = self.bootstrap(home, "--apply", "--target", target, stubs=self.stub_clis(root))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for path in expected[target]:
                    self.assertTrue((home / path).exists(), f"{path} missing for {target}")
                self.assertFalse((home / other[target]).exists(), "the other provider was touched")

    def test_a_whole_directory_link_is_never_written_through(self) -> None:
        # An older layout linked ~/.agents/skills as one directory. Descending
        # into that link writes entries into the repository it points at.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            predecessor = root / "old/codex-config/skills"
            (predecessor / "legacy-skill").mkdir(parents=True)
            (home / ".agents").mkdir(parents=True)
            (home / ".agents/skills").symlink_to(predecessor)
            stubs = self.stub_clis(root)

            refused = self.bootstrap(home, "--apply", "--target", "codex", stubs=stubs)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("whole-directory link", refused.stderr)
            self.assertEqual(len(list(predecessor.iterdir())), 1, "wrote into the predecessor")

            adopted = self.bootstrap(home, "--apply", "--adopt", "--target", "codex", stubs=stubs)
            self.assertEqual(adopted.returncode, 0, adopted.stdout + adopted.stderr)
            self.assertEqual(len(list(predecessor.iterdir())), 1, "wrote into the predecessor")
            self.assertFalse((home / ".agents/skills").is_symlink())
            self.assertTrue((home / ".agents/skills/writing-plans").exists())

    def test_adoption_repoints_predecessors_but_not_foreign_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            predecessor = root / "old/codex-config"
            (predecessor / ".codex/agents").mkdir(parents=True)
            (predecessor / "AGENTS.global.md").write_text("old\n")
            (home / ".codex").mkdir(parents=True)
            (home / ".codex/AGENTS.md").symlink_to(predecessor / "AGENTS.global.md")
            (home / ".codex/hooks.json").symlink_to("/etc/hostname")
            stubs = self.stub_clis(root)

            refused = self.bootstrap(home, "--apply", "--target", "codex", stubs=stubs)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("adoptable", refused.stderr)
            self.assertIn("--adopt", refused.stderr)
            self.assertEqual(
                (home / ".codex/AGENTS.md").readlink(), predecessor / "AGENTS.global.md"
            )

            adopted = self.bootstrap(home, "--apply", "--adopt", "--target", "codex", stubs=stubs)
            self.assertNotEqual(adopted.returncode, 0, "the foreign link must stay a conflict")
            self.assertEqual((home / ".codex/AGENTS.md").readlink(), ROOT / "AGENTS.global.md")
            self.assertEqual((home / ".codex/hooks.json").readlink(), Path("/etc/hostname"))

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
            for name in ("python3", "bash", "dirname", "uname", "cmp", "mkdir", "ln", "basename"):
                source = shutil.which(name)
                if source:
                    (bin_dir / name).symlink_to(
                        sys.executable if name == "python3" else source
                    )
            # An explicit target must still preflight its own CLI. Without one,
            # inference now fails earlier with its own message.
            result = subprocess.run(
                ["/bin/bash", str(ROOT / "scripts/bootstrap.sh"), "--apply", "--target", "claude"],
                env={"HOME": str(home), "PATH": str(bin_dir), "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Claude Code CLI is required", result.stderr)
            self.assertFalse((home / ".claude").exists())

            inferred = subprocess.run(
                ["/bin/bash", str(ROOT / "scripts/bootstrap.sh"), "--apply"],
                env={"HOME": str(home), "PATH": str(bin_dir), "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(inferred.returncode, 0)
            self.assertIn("No Codex or Claude Code CLI found", inferred.stderr)
            self.assertFalse((home / ".claude").exists())


if __name__ == "__main__":
    unittest.main()

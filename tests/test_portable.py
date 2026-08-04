from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
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

    def test_fable_is_default_and_implementation_uses_opus(self) -> None:
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["model"], "claude-fable-5")
        agents = {
            data["name"]: data
            for path in (ROOT / ".claude/agents").glob("*.md")
            if (data := frontmatter(path))
        }
        implementation = {
            "implementer",
            "implementer-fast",
            "implementer-standard",
            "implementer-deep",
        }
        self.assertEqual(
            {name for name, data in agents.items() if data["model"] == "claude-opus-5"},
            implementation,
        )
        self.assertTrue(
            all(
                data["model"] == "claude-fable-5"
                for name, data in agents.items()
                if name not in implementation
            )
        )


class SharedSkillTests(unittest.TestCase):
    # One copy of each skill serves both providers. The port forked these files
    # and three defects followed, so a one-sided edit must fail here rather than
    # silently reintroduce the fork.
    DISPATCH_FILES = (
        "skills/requesting-code-review/SKILL.md",
        "skills/requesting-code-review/code-reviewer.md",
        "skills/subagent-driven-development/SKILL.md",
        "skills/subagent-driven-development/implementer-prompt.md",
        "skills/subagent-driven-development/task-reviewer-prompt.md",
    )

    def test_dispatch_documentation_covers_both_providers(self) -> None:
        for name in self.DISPATCH_FILES:
            with self.subTest(file=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn("Codex", text)
                self.assertIn("Claude Code", text)

    def test_no_skill_is_duplicated_per_provider(self) -> None:
        skills = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
        for suffix in ("-codex", "-claude", "_codex", "_claude"):
            forked = {name for name in skills if name.endswith(suffix)}
            self.assertEqual(forked, set(), f"per-provider skill fork: {forked}")

    def test_both_provider_agent_manifests_are_present(self) -> None:
        # The port deleted the Codex per-skill manifests; losing them again
        # would silently drop Codex agent routing for those skills.
        self.assertGreater(len(list((ROOT / "skills").glob("*/agents/openai.yaml"))), 0)
        self.assertGreater(len(list((ROOT / ".codex/agents").glob("*.toml"))), 0)
        self.assertGreater(len(list((ROOT / ".claude/agents").glob("*.md"))), 0)

    def test_scientific_ecc_sources_are_narrow_and_pinned(self) -> None:
        with (ROOT / "sources.lock.toml").open("rb") as handle:
            sources = tomllib.load(handle)["sources"]
        ecc = next((source for source in sources if source["name"] == "ecc"), None)
        self.assertIsNotNone(ecc, "missing pinned ECC source")
        self.assertEqual(ecc["repository"], "https://github.com/affaan-m/ECC")
        self.assertRegex(ecc["commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(ecc["commit"], "7a5757e6c0d7e8e1080d30169b4b044d76e0f7fc")
        self.assertEqual(ecc["license"], "MIT")
        self.assertEqual(
            ecc["items"],
            ["deep-research", "eval-harness", "unified-memory", "strategic-compact", "mle-workflow"],
        )
        self.assertEqual(
            ecc["adaptations"],
            ["scientific-research", "research-eval", "research-memory", "research-compact", "scientific-ml"],
        )

        with (ROOT / "capability-bundle.toml").open("rb") as handle:
            components = tomllib.load(handle)["components"]
        scientific = {
            item["name"]: item
            for item in components
            if item["name"] in set(ecc["adaptations"])
        }
        self.assertEqual(set(scientific), set(ecc["adaptations"]))
        for name, item in scientific.items():
            self.assertEqual(item["kind"], "skill")
            self.assertEqual(item["classification"], "supported")
            self.assertEqual(item["path"], f"skills/{name}")
            skill = ROOT / item["path"] / "SKILL.md"
            self.assertEqual(frontmatter(skill)["name"], name)
            text = skill.read_text(encoding="utf-8")
            self.assertIn(ecc["commit"], text)
            self.assertIn("Adapted", text)

        forbidden_kinds = {"plugin", "hook", "command", "rule", "agent", "mcp", "dashboard", "runtime"}
        self.assertFalse(
            [item for item in components if item.get("source") == "ecc" and item["kind"] in forbidden_kinds]
        )

        bodies = {
            name: (ROOT / item["path"] / "SKILL.md").read_text(encoding="utf-8")
            for name, item in scientific.items()
        }
        self.assertIn("durable cited Markdown", bodies["scientific-research"])
        self.assertIn("recorded verdict", bodies["research-eval"])
        self.assertIn("unreviewed context", bodies["research-memory"])
        self.assertIn("reference existing artifacts", bodies["research-compact"].lower())
        self.assertIn("redact", bodies["research-compact"].lower())
        self.assertIn("single question", bodies["scientific-ml"])
        self.assertIn("reproduc", bodies["scientific-ml"].lower())

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in ecc["adaptations"]:
            self.assertIn(f"`{name}`", readme)
        self.assertIn("scripts/update.sh --review ecc", readme)
        self.assertIn("never applies updates automatically", readme)


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


class EccUpdateReviewTests(unittest.TestCase):
    def git(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def make_upstream(self, root: Path) -> tuple[Path, str, str]:
        repo = root / "ecc-upstream"
        repo.mkdir()
        self.git(repo, "init", "-b", "main")
        self.git(repo, "config", "user.name", "ECC Test")
        self.git(repo, "config", "user.email", "ecc-test@example.invalid")
        adopted = repo / "skills/deep-research/SKILL.md"
        adopted.parent.mkdir(parents=True)
        adopted.write_text("version one\n", encoding="utf-8")
        (repo / "README.md").write_text("unrelated one\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "initial")
        pinned = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        adopted.write_text("version two\n", encoding="utf-8")
        (repo / "README.md").write_text("unrelated two\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "update")
        candidate = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        return repo, pinned, candidate

    def write_lock(self, path: Path, repository: Path, commit: str, *, include_ecc: bool = True) -> None:
        if include_ecc:
            path.write_text(
                "\n".join(
                    (
                        "version = 1",
                        "[[sources]]",
                        'name = "ecc"',
                        f'repository = "{repository}"',
                        f'commit = "{commit}"',
                        'license = "MIT"',
                        'items = ["deep-research", "eval-harness", "unified-memory", "strategic-compact", "mle-workflow"]',
                    )
                )
                + "\n",
                encoding="utf-8",
            )
        else:
            path.write_text("version = 1\nsources = []\n", encoding="utf-8")

    def test_review_reports_only_adopted_paths_without_mutating_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, pinned, candidate = self.make_upstream(root)
            lock = root / "sources.lock.toml"
            self.write_lock(lock, repo, pinned)
            lock_before = lock.read_bytes()
            status_before = self.git(repo, "status", "--porcelain=v1").stdout

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/review_ecc_updates.py"),
                    "--lock",
                    str(lock),
                    "--candidate",
                    candidate,
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(pinned, result.stdout)
            self.assertIn(candidate, result.stdout)
            self.assertIn("M\tskills/deep-research/SKILL.md", result.stdout)
            self.assertNotIn("README.md", result.stdout)
            self.assertIn("does not modify", result.stdout)
            self.assertEqual(lock.read_bytes(), lock_before)
            self.assertEqual(self.git(repo, "status", "--porcelain=v1").stdout, status_before)

    def test_review_fails_closed_when_ecc_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / "sources.lock.toml"
            self.write_lock(lock, root, "0" * 40, include_ecc=False)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/review_ecc_updates.py"), "--lock", str(lock)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ECC source", result.stderr)

    def test_review_distinguishes_unrelated_only_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, pinned, _ = self.make_upstream(root)
            (repo / "skills/deep-research/SKILL.md").write_text("version one\n", encoding="utf-8")
            (repo / "README.md").write_text("unrelated three\n", encoding="utf-8")
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", "unrelated only from pin")
            candidate = self.git(repo, "rev-parse", "HEAD").stdout.strip()
            lock = root / "sources.lock.toml"
            self.write_lock(lock, repo, pinned)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/review_ecc_updates.py"),
                    "--lock",
                    str(lock),
                    "--candidate",
                    candidate,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("changed only outside", result.stdout)
            self.assertNotIn("README.md", result.stdout)

    def test_update_script_dispatches_ecc_review_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, pinned, candidate = self.make_upstream(root)
            lock = root / "sources.lock.toml"
            self.write_lock(lock, repo, pinned)
            result = subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts/update.sh"),
                    "--review",
                    "ecc",
                    "--lock",
                    str(lock),
                    "--candidate",
                    candidate,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("skills/deep-research/SKILL.md", result.stdout)


if __name__ == "__main__":
    unittest.main()

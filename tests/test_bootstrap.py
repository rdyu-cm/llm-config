import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PortableSkillInventoryTests(unittest.TestCase):
    def test_execution_skills_include_required_payloads(self) -> None:
        expected = {
            "executing-plans": {"SKILL.md"},
            "subagent-driven-development": {
                "SKILL.md",
                "implementer-prompt.md",
                "task-reviewer-prompt.md",
                "scripts/review-package",
                "scripts/sdd-workspace",
                "scripts/task-brief",
            },
            "using-git-worktrees": {"SKILL.md"},
        }

        for skill_name, relative_paths in expected.items():
            skill_root = ROOT / "skills" / skill_name
            observed = {
                str(path.relative_to(skill_root)) for path in skill_root.rglob("*") if path.is_file()
            }
            self.assertEqual(observed, relative_paths)

        for script_name in ("review-package", "sdd-workspace", "task-brief"):
            script = ROOT / "skills" / "subagent-driven-development" / "scripts" / script_name
            self.assertTrue(os.access(script, os.X_OK), f"not executable: {script_name}")


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_update_check = os.environ.get("CODEX_CONFIG_UPDATE_CHECK")
        os.environ["CODEX_CONFIG_UPDATE_CHECK"] = "0"

    def tearDown(self) -> None:
        if self.previous_update_check is None:
            os.environ.pop("CODEX_CONFIG_UPDATE_CHECK", None)
        else:
            os.environ["CODEX_CONFIG_UPDATE_CHECK"] = self.previous_update_check

    def make_lean_fixture(self, directory: str) -> tuple[Path, Path, Path]:
        fixture = Path(directory) / "fixture"
        home = Path(directory) / "home"
        fake_bin = Path(directory) / "bin"
        (fixture / "scripts").mkdir(parents=True)
        (fixture / ".codex/hooks").mkdir(parents=True)
        (fixture / ".codex/agents").mkdir()
        (fixture / "skills").mkdir()
        (fixture / "profiles").mkdir()
        home.mkdir()
        fake_bin.mkdir()
        npx = fake_bin / "npx"
        npx.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        npx.chmod(0o755)
        for name in ("bootstrap.sh", "sync_config.py", "cleanup_legacy_gstack.py"):
            shutil.copy(ROOT / "scripts" / name, fixture / "scripts" / name)
        (fixture / ".codex/config.toml").write_text(
            'sandbox_mode = "workspace-write"\n', encoding="utf-8"
        )
        (fixture / ".codex/hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
        (fixture / "AGENTS.global.md").write_text("# Global instructions\n", encoding="utf-8")
        (fixture / "profiles/minimal.config.toml").write_text("", encoding="utf-8")
        return fixture, home, fake_bin

    def test_obsolete_gstack_flag_is_rejected(self) -> None:
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/bootstrap.sh"), "--gstack=off"],
            env={**os.environ, "PYTHON": sys.executable},
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)

    def test_apply_cleans_exact_legacy_links_in_one_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, home, fake_bin = self.make_lean_fixture(directory)
            source = fixture / "retired-source"
            source.mkdir()
            target = home / ".codex/skills/gstack-example"
            target.parent.mkdir(parents=True)
            target.symlink_to(source, target_is_directory=True)
            state = home / ".codex/gstack-managed.json"
            state.write_text(
                '{"version": 1, "mode": "full", "links": {'
                f'"{target}": "{source}"'
                "}}",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["bash", str(fixture / "scripts/bootstrap.sh"), "--apply"],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PYTHON": sys.executable,
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(target.is_symlink())
            self.assertFalse(state.exists())
            self.assertTrue((home / ".codex/AGENTS.md").is_symlink())

    def test_legacy_cleanup_conflict_stops_before_discovery_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture, home, fake_bin = self.make_lean_fixture(directory)
            target = home / ".codex/skills/gstack-example"
            target.parent.mkdir(parents=True)
            target.write_text("mine", encoding="utf-8")
            state = home / ".codex/gstack-managed.json"
            state.write_text(
                '{"version": 1, "mode": "full", "links": {'
                f'"{target}": "{fixture / "retired-source"}"'
                "}}",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["bash", str(fixture / "scripts/bootstrap.sh"), "--apply"],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PYTHON": sys.executable,
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                },
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "mine")
            self.assertTrue(state.exists())
            self.assertFalse((home / ".codex/AGENTS.md").exists())

    def test_powershell_bootstrap_uses_shared_cleanup_helper(self) -> None:
        text = (ROOT / "scripts/bootstrap.ps1").read_text(encoding="utf-8")

        self.assertIn('"scripts/cleanup_legacy_gstack.py"', text)
        self.assertRegex(
            text,
            r"(?s)if \(\$Apply\).*& \$Python \$cleanup --home \$HOME --apply",
        )

    def test_bootstrap_rejects_duplicate_actions_and_unknown_options(self) -> None:
        for args in (("--dry-run", "--apply"), ("--unknown",)):
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/bootstrap.sh"), *args],
                env={**os.environ, "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_apply_creates_codex_directory_in_clean_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            home = Path(directory) / "home"
            fake_bin = Path(directory) / "bin"
            npx_log = Path(directory) / "npx.log"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / ".codex" / "hooks").mkdir(parents=True)
            (fixture / ".codex" / "agents").mkdir()
            (fixture / "skills").mkdir()
            (fixture / "profiles").mkdir()
            home.mkdir()
            fake_bin.mkdir()
            fake_npx = fake_bin / "npx"
            fake_npx.write_text(
                "#!/usr/bin/env bash\n"
                'printf "%s\\n" "$*" >> "$NPX_LOG"\n'
                "if IFS= read -r _; then exit 97; fi\n",
                encoding="utf-8",
            )
            fake_npx.chmod(0o755)
            shutil.copy(ROOT / "scripts" / "bootstrap.sh", fixture / "scripts" / "bootstrap.sh")
            shutil.copy(ROOT / "scripts" / "sync_config.py", fixture / "scripts" / "sync_config.py")
            shutil.copy(ROOT / "scripts" / "cleanup_legacy_gstack.py", fixture / "scripts" / "cleanup_legacy_gstack.py")
            (fixture / ".codex" / "config.toml").write_text(
                'sandbox_mode = "workspace-write"\n', encoding="utf-8"
            )
            (fixture / ".codex" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (fixture / "AGENTS.global.md").write_text("# Global instructions\n", encoding="utf-8")
            (fixture / "profiles" / "minimal.config.toml").write_text("", encoding="utf-8")

            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--apply"],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PYTHON": sys.executable,
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                    "NPX_LOG": str(npx_log),
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            active = home / ".codex" / "config.toml"
            self.assertFalse(active.is_symlink())
            self.assertEqual(
                active.read_text(encoding="utf-8"),
                (fixture / ".codex" / "config.generated.toml").read_text(encoding="utf-8"),
            )
            self.assertEqual((home / ".agents" / "skills").resolve(), fixture / "skills")
            self.assertTrue(npx_log.exists(), "bootstrap did not invoke npx")
            self.assertEqual(
                npx_log.read_text(encoding="utf-8"),
                "-y codebase-memory-mcp@0.8.1\n",
            )

    def test_apply_replaces_managed_config_symlink_with_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            home = Path(directory) / "home"
            fake_bin = Path(directory) / "bin"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / ".codex" / "hooks").mkdir(parents=True)
            (fixture / ".codex" / "agents").mkdir()
            (fixture / "skills").mkdir()
            (fixture / "profiles").mkdir()
            (home / ".codex").mkdir(parents=True)
            fake_bin.mkdir()
            fake_npx = fake_bin / "npx"
            fake_npx.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_npx.chmod(0o755)
            shutil.copy(ROOT / "scripts" / "bootstrap.sh", fixture / "scripts" / "bootstrap.sh")
            shutil.copy(ROOT / "scripts" / "sync_config.py", fixture / "scripts" / "sync_config.py")
            shutil.copy(ROOT / "scripts" / "cleanup_legacy_gstack.py", fixture / "scripts" / "cleanup_legacy_gstack.py")
            (fixture / ".codex" / "config.toml").write_text(
                'sandbox_mode = "workspace-write"\n', encoding="utf-8"
            )
            generated = fixture / ".codex" / "config.generated.toml"
            generated.write_text(
                "# Generated by scripts/sync_config.py; do not edit directly.\n"
                'sandbox_mode = "workspace-write"\n',
                encoding="utf-8",
            )
            (home / ".codex" / "config.local.toml").write_text(
                'approvals_reviewer = "auto_review"\n',
                encoding="utf-8",
            )
            (home / ".codex" / "config.toml").symlink_to(generated)
            (fixture / ".codex" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (fixture / "AGENTS.global.md").write_text("# Global instructions\n", encoding="utf-8")
            (fixture / "profiles" / "minimal.config.toml").write_text("", encoding="utf-8")

            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--apply"],
                env={
                    **os.environ,
                    "CODEX_CONFIG_UPDATE_CHECK": "0",
                    "HOME": str(home),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                    "PYTHON": sys.executable,
                },
                capture_output=True,
                text=True,
            )

            active = home / ".codex" / "config.toml"
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(active.is_symlink())
            with active.open("rb") as handle:
                config = tomllib.load(handle)
            self.assertEqual(config["approvals_reviewer"], "auto_review")
            self.assertEqual(config["sandbox_mode"], "workspace-write")

            with active.open("a", encoding="utf-8") as handle:
                handle.write('\n[hooks.state.example]\ntrusted_hash = "sha256:test"\n')
            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--apply"],
                env={
                    **os.environ,
                    "CODEX_CONFIG_UPDATE_CHECK": "0",
                    "HOME": str(home),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                    "PYTHON": sys.executable,
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            with active.open("rb") as handle:
                config = tomllib.load(handle)
            self.assertEqual(config["approvals_reviewer"], "auto_review")
            self.assertEqual(
                config["hooks"]["state"]["example"]["trusted_hash"],
                "sha256:test",
            )

    def test_dry_run_does_not_prewarm_codebase_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            fake_bin = Path(directory) / "bin"
            home.mkdir()
            fake_bin.mkdir()
            npx_log = Path(directory) / "npx.log"
            fake_npx = fake_bin / "npx"
            fake_npx.write_text(
                "#!/usr/bin/env bash\n"
                'printf "%s\\n" "$*" >> "$NPX_LOG"\n',
                encoding="utf-8",
            )
            fake_npx.chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "bootstrap.sh"), "--dry-run"],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PYTHON": sys.executable,
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                    "NPX_LOG": str(npx_log),
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(npx_log.exists())

    def test_failed_merge_leaves_existing_config_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            home = Path(directory) / "home"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / ".codex").mkdir()
            (home / ".codex").mkdir(parents=True)
            shutil.copy(ROOT / "scripts" / "bootstrap.sh", fixture / "scripts" / "bootstrap.sh")
            shutil.copy(ROOT / "scripts" / "sync_config.py", fixture / "scripts" / "sync_config.py")
            shutil.copy(ROOT / "scripts" / "cleanup_legacy_gstack.py", fixture / "scripts" / "cleanup_legacy_gstack.py")
            (fixture / ".codex" / "config.toml").write_text("invalid =\n", encoding="utf-8")
            active = home / ".codex" / "config.toml"
            active.write_text('model = "cluster-model"\n', encoding="utf-8")

            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--apply"],
                env={**os.environ, "HOME": str(home), "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(active.is_symlink())
            self.assertEqual(active.read_text(encoding="utf-8"), 'model = "cluster-model"\n')
            self.assertFalse((home / ".codex" / "config.local.toml").exists())
            self.assertFalse((fixture / ".codex" / "config.generated.toml").exists())
            self.assertFalse((home / ".codex" / "AGENTS.md").exists())

if __name__ == "__main__":
    unittest.main()

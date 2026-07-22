import os
import shutil
import subprocess
import sys
import tempfile
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

    def test_gstack_flags_accept_unordered_permutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            for args in (("--gstack=workflow", "--dry-run"), ("--dry-run", "--gstack=full")):
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts/bootstrap.sh"), *args],
                    env={**os.environ, "HOME": str(home), "PYTHON": sys.executable},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_bootstrap_rejects_duplicate_actions_gstack_flags_and_unknown_options(self) -> None:
        for args in (("--dry-run", "--apply"), ("--gstack=off", "--gstack=workflow"), ("--unknown",)):
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/bootstrap.sh"), *args],
                env={**os.environ, "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_dry_run_does_not_invoke_bun_curl_or_npx(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            fake_bin = Path(directory) / "bin"
            command_log = Path(directory) / "commands.log"
            home.mkdir()
            fake_bin.mkdir()
            for command in ("bun", "curl", "npx"):
                executable = fake_bin / command
                executable.write_text(
                    "#!/usr/bin/env bash\n"
                    'printf "%s\\n" "$0" >> "$COMMAND_LOG"\n'
                    "exit 99\n",
                    encoding="utf-8",
                )
                executable.chmod(0o755)
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/bootstrap.sh"), "--dry-run", "--gstack=full"],
                env={**os.environ, "HOME": str(home), "PYTHON": sys.executable, "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}", "COMMAND_LOG": str(command_log)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(command_log.exists())
    def test_gstack_prepare_and_install_failures_propagate_and_dry_run_omits_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            home = Path(directory) / "home"
            logs = Path(directory) / "logs"
            (fixture / "scripts").mkdir(parents=True)
            home.mkdir()
            logs.mkdir()
            shutil.copy(ROOT / "scripts" / "bootstrap.sh", fixture / "scripts" / "bootstrap.sh")
            for name in ("prepare_gstack.py", "install_gstack.py"):
                (fixture / "scripts" / name).write_text(
                    "import os, sys\n"
                    "from pathlib import Path\n"
                    "name = Path(sys.argv[0]).stem\n"
                    "Path(os.environ['LOG_DIR'], name).write_text(' '.join(sys.argv[1:]))\n"
                    "raise SystemExit(41 if os.environ.get('FAIL_' + name.upper()) else 0)\n",
                    encoding="utf-8",
                )
            base_env = {**os.environ, "HOME": str(home), "PYTHON": sys.executable, "LOG_DIR": str(logs)}
            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--dry-run", "--gstack=workflow"],
                env=base_env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("--apply", (logs / "prepare_gstack").read_text())
            self.assertNotIn("--apply", (logs / "install_gstack").read_text())
            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--dry-run"],
                env={**base_env, "FAIL_PREPARE_GSTACK": "1"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 41)
            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--dry-run"],
                env={**base_env, "FAIL_INSTALL_GSTACK": "1"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 41)
    def test_gstack_modes_are_accepted_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()

            for mode in ("off", "workflow", "full"):
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts/bootstrap.sh"), "--dry-run", f"--gstack={mode}"],
                    env={**os.environ, "HOME": str(home), "PYTHON": sys.executable},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"gstack mode: {mode}", result.stdout)

    def test_invalid_gstack_mode_exits_with_usage_error(self) -> None:
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/bootstrap.sh"), "--gstack=invalid"],
            env={**os.environ, "PYTHON": sys.executable},
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)

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
            shutil.copy(ROOT / "scripts" / "prepare_gstack.py", fixture / "scripts" / "prepare_gstack.py")
            shutil.copy(ROOT / "scripts" / "install_gstack.py", fixture / "scripts" / "install_gstack.py")
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
            self.assertEqual(
                (home / ".codex" / "config.toml").resolve(),
                fixture / ".codex" / "config.generated.toml",
            )
            self.assertEqual((home / ".agents" / "skills").resolve(), fixture / "skills")
            self.assertTrue(npx_log.exists(), "bootstrap did not invoke npx")
            self.assertEqual(
                npx_log.read_text(encoding="utf-8"),
                "-y codebase-memory-mcp@0.8.1\n",
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
            shutil.copy(ROOT / "scripts" / "prepare_gstack.py", fixture / "scripts" / "prepare_gstack.py")
            shutil.copy(ROOT / "scripts" / "install_gstack.py", fixture / "scripts" / "install_gstack.py")
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
            self.assertFalse((home / ".codex" / "gstack-managed.json").exists())


    def test_apply_gstack_conflict_stops_before_bootstrap_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            fake_bin = Path(directory) / "bin"
            home.mkdir()
            (home / ".codex/skills/gstack-office-hours").mkdir(parents=True)
            fake_bin.mkdir()
            npx = fake_bin / "npx"
            npx.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            npx.chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "scripts/bootstrap.sh"), "--apply", "--gstack=workflow"],
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

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((home / ".codex/config.toml").exists())
            self.assertTrue((home / ".agents/skills").exists())

    def test_prewarm_failure_leaves_gstack_uninstalled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            fake_bin = Path(directory) / "bin"
            home.mkdir()
            fake_bin.mkdir()
            npx = fake_bin / "npx"
            npx.write_text("#!/usr/bin/env bash\nexit 73\n", encoding="utf-8")
            npx.chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "scripts/bootstrap.sh"), "--apply", "--gstack=off"],
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

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((home / ".codex/gstack-managed.json").exists())
            self.assertFalse((home / ".codex/skills/gstack-office-hours").exists())

if __name__ == "__main__":
    unittest.main()

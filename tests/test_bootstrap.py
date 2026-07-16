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
    def test_apply_creates_codex_directory_in_clean_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            home = Path(directory) / "home"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / ".codex" / "hooks").mkdir(parents=True)
            (fixture / ".codex" / "agents").mkdir()
            (fixture / "skills").mkdir()
            (fixture / "profiles").mkdir()
            home.mkdir()
            shutil.copy(ROOT / "scripts" / "bootstrap.sh", fixture / "scripts" / "bootstrap.sh")
            shutil.copy(ROOT / "scripts" / "sync_config.py", fixture / "scripts" / "sync_config.py")
            (fixture / ".codex" / "config.toml").write_text(
                'sandbox_mode = "workspace-write"\n', encoding="utf-8"
            )
            (fixture / ".codex" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (fixture / "AGENTS.global.md").write_text("# Global instructions\n", encoding="utf-8")
            (fixture / "profiles" / "minimal.config.toml").write_text("", encoding="utf-8")

            result = subprocess.run(
                ["bash", str(fixture / "scripts" / "bootstrap.sh"), "--apply"],
                env={**os.environ, "HOME": str(home), "PYTHON": sys.executable},
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (home / ".codex" / "config.toml").resolve(),
                fixture / ".codex" / "config.generated.toml",
            )
            self.assertEqual((home / ".agents" / "skills").resolve(), fixture / "skills")

    def test_failed_merge_leaves_existing_config_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            home = Path(directory) / "home"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / ".codex").mkdir()
            (home / ".codex").mkdir(parents=True)
            shutil.copy(ROOT / "scripts" / "bootstrap.sh", fixture / "scripts" / "bootstrap.sh")
            shutil.copy(ROOT / "scripts" / "sync_config.py", fixture / "scripts" / "sync_config.py")
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

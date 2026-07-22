import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import scripts.install_gstack as installer
from scripts.install_gstack import install


ROOT = Path(__file__).resolve().parents[1]


class InstallGstackTests(unittest.TestCase):
    def test_workflow_links_only_allowlisted_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            install(ROOT, home, "workflow", True)
            self.assertTrue((home / ".codex/skills/gstack-office-hours").is_symlink())
            self.assertFalse((home / ".codex/skills/gstack-browse").exists())
            state = json.loads((home / ".codex/gstack-managed.json").read_text())
            self.assertEqual(state["mode"], "workflow")

    def test_switching_full_to_workflow_removes_only_managed_browser_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            unrelated = home / ".codex/skills/user-skill"
            unrelated.mkdir(parents=True)
            install(ROOT, home, "full", True)
            self.assertTrue((home / ".codex/skills/gstack-browse").exists())
            install(ROOT, home, "workflow", True)
            self.assertFalse((home / ".codex/skills/gstack-browse").exists())
            self.assertTrue(unrelated.is_dir())

    def test_dry_run_and_conflicts_do_not_mutate_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            conflict = home / ".codex/skills/gstack-office-hours"
            conflict.mkdir(parents=True)
            messages = install(ROOT, home, "workflow", False)
            self.assertTrue(any("conflict" in line for line in messages))
            self.assertFalse((home / ".codex/gstack-managed.json").exists())



    def test_reinstalling_a_profile_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            install(ROOT, home, "workflow", True)
            state = (home / ".codex/gstack-managed.json").read_text()

            self.assertEqual(install(ROOT, home, "workflow", True), [])
            self.assertEqual((home / ".codex/gstack-managed.json").read_text(), state)

    def test_off_removes_only_managed_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            unrelated = home / ".codex/skills/user-skill"
            unrelated.mkdir(parents=True)
            install(ROOT, home, "workflow", True)

            install(ROOT, home, "off", True)

            self.assertFalse((home / ".codex/skills/gstack-office-hours").exists())
            self.assertTrue(unrelated.is_dir())
            state = json.loads((home / ".codex/gstack-managed.json").read_text())
            self.assertEqual(state["mode"], "off")

    def test_parent_symlink_conflict_does_not_create_external_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            external = home / "external"
            external.mkdir()
            skills = home / ".codex/skills"
            skills.mkdir(parents=True)
            (skills / "gstack").symlink_to(external, target_is_directory=True)

            messages = install(ROOT, home, "workflow", True)

            self.assertTrue(any("conflict" in line for line in messages))
            self.assertEqual(list(external.iterdir()), [])
            self.assertFalse((home / ".codex/gstack-managed.json").exists())

    def test_state_symlink_conflict_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home / ".codex/gstack-managed.json"
            state.parent.mkdir(parents=True)
            state.symlink_to(home / "missing-state")

            messages = install(ROOT, home, "workflow", True)

            self.assertTrue(any("conflict" in line for line in messages))
            self.assertTrue(state.is_symlink())

    def test_failed_state_write_restores_removed_links_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            install(ROOT, home, "full", True)
            state_path = home / ".codex/gstack-managed.json"
            previous_state = state_path.read_bytes()
            browse = home / ".codex/skills/gstack-browse"

            with patch.object(installer, "_write_state", side_effect=OSError("write failed")):
                with self.assertRaisesRegex(OSError, "write failed"):
                    install(ROOT, home, "workflow", True)

            self.assertTrue(browse.is_symlink())
            self.assertEqual(state_path.read_bytes(), previous_state)

    def test_cli_reports_install_errors(self) -> None:
        stderr = StringIO()
        with patch("sys.argv", ["install_gstack.py", "--root", "/missing", "--mode", "workflow", "--apply"]):
            with redirect_stderr(stderr):
                self.assertEqual(installer.main(), 1)
        self.assertIn("gstack install failed:", stderr.getvalue())

    def test_parent_file_conflict_does_not_mutate_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            skills = home / ".codex/skills"
            skills.mkdir(parents=True)
            (skills / "gstack").write_text("not a directory")

            messages = install(ROOT, home, "workflow", True)

            self.assertTrue(any("conflict" in line for line in messages))
            self.assertFalse((home / ".codex/gstack-managed.json").exists())

if __name__ == "__main__":
    unittest.main()

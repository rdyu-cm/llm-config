import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

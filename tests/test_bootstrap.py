import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
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

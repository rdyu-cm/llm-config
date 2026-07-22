import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_gstack import prepare


ROOT = Path(__file__).resolve().parents[1]


class PrepareGstackTests(unittest.TestCase):
    def test_off_does_not_require_bun(self) -> None:
        self.assertEqual(prepare(ROOT, "off", True, {"PATH": ""}), [])

    def test_workflow_sets_browser_download_skip(self) -> None:
        with patch("scripts.prepare_gstack.find_bun", return_value=Path("/fake/bun")), \
             patch("scripts.prepare_gstack.subprocess.run") as run:
            prepare(ROOT, "workflow", True, {"PATH": "/fake"})
        install_call = run.call_args_list[0]
        self.assertEqual(install_call.args[0][-2:], ["install", "--frozen-lockfile"])
        self.assertEqual(install_call.kwargs["env"]["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"], "1")
        self.assertFalse(any("build" in call.args[0] for call in run.call_args_list))

    def test_checksum_mismatch_stops_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             patch("scripts.prepare_gstack.find_bun", return_value=None), \
             patch("scripts.prepare_gstack.download_installer", return_value=Path(directory) / "bun-install"):
            installer = Path(directory) / "bun-install"
            installer.write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                prepare(ROOT, "workflow", True, {"PATH": ""})

if __name__ == "__main__":
    unittest.main()

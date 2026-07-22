import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_gstack import prepare


ROOT = Path(__file__).resolve().parents[1]


class PrepareGstackTests(unittest.TestCase):
    def test_off_does_not_require_bun(self) -> None:
        self.assertEqual(prepare(ROOT, "off", True, {"PATH": ""}), [])

    def test_workflow_apply_requires_no_bun_or_subprocess(self) -> None:
        with patch("scripts.prepare_gstack.find_bun") as find_bun, \
             patch("scripts.prepare_gstack.download_installer") as download, \
             patch("scripts.prepare_gstack.subprocess.run") as run:
            self.assertEqual(prepare(ROOT, "workflow", True, {"PATH": ""}), ["ready   gstack workflow"])
        find_bun.assert_not_called()
        download.assert_not_called()
        run.assert_not_called()

    def test_checksum_mismatch_stops_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             patch("scripts.prepare_gstack.find_bun", return_value=None), \
             patch("scripts.prepare_gstack.download_installer", return_value=Path(directory) / "bun-install"):
            installer = Path(directory) / "bun-install"
            installer.write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                prepare(ROOT, "full", True, {"PATH": ""})

    def test_verified_installer_runs_before_frozen_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(directory) / "bun-install"
            installer.write_text("installer", encoding="utf-8")
            events: list[str] = []
            with patch("scripts.prepare_gstack.find_bun", side_effect=[None, Path("/fake/bun")]), \
                 patch("scripts.prepare_gstack.download_installer", return_value=installer), \
                 patch("scripts.prepare_gstack.verify_sha256", side_effect=lambda *_: events.append("verify")), \
                 patch("scripts.prepare_gstack.run_bun_installer", side_effect=lambda *_: events.append("installer")), \
                 patch("scripts.prepare_gstack.subprocess.run", side_effect=lambda *_args, **_kwargs: events.append("install")):
                prepare(ROOT, "full", True, {"PATH": "", "HOME": directory})
            self.assertEqual(events[:3], ["verify", "installer", "install"])

    def test_full_installs_before_build(self) -> None:
        with patch("scripts.prepare_gstack.find_bun", return_value=Path("/fake/bun")), \
             patch("scripts.prepare_gstack.subprocess.run") as run:
            prepare(ROOT, "full", True, {"PATH": ""})
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ["install", "run", "x"])
        self.assertEqual(run.call_args_list[0].args[0][-2:], ["install", "--frozen-lockfile"])
        self.assertEqual(run.call_args_list[1].args[0], ["/fake/bun", "run", "build"])

    def test_dry_run_never_installs_chromium(self) -> None:
        with patch("scripts.prepare_gstack.find_bun", return_value=Path("/fake/bun")), \
             patch("scripts.prepare_gstack.subprocess.run") as run:
            for mode in ("workflow", "full"):
                prepare(ROOT, mode, False, {"PATH": ""})

        run.assert_not_called()


    def test_full_installs_chromium_after_build(self) -> None:
        with patch("scripts.prepare_gstack.find_bun", return_value=Path("/fake/bun")), \
             patch("scripts.prepare_gstack.subprocess.run") as run:
            prepare(ROOT, "full", True, {"PATH": ""})

        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["/fake/bun", "install", "--frozen-lockfile"],
                ["/fake/bun", "run", "build"],
                ["/fake/bun", "x", "playwright", "install", "chromium"],
            ],
        )
    def test_installer_is_removed_after_checksum_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(directory) / "bun-install"
            installer.write_text("unexpected", encoding="utf-8")
            with patch("scripts.prepare_gstack.find_bun", return_value=None), \
                 patch("scripts.prepare_gstack.download_installer", return_value=installer):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    prepare(ROOT, "full", True, {"PATH": ""})
            self.assertFalse(installer.exists())

    def test_installer_is_removed_after_execution_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(directory) / "bun-install"
            installer.write_text("installer", encoding="utf-8")
            with patch("scripts.prepare_gstack.find_bun", return_value=None), \
                 patch("scripts.prepare_gstack.download_installer", return_value=installer), \
                 patch("scripts.prepare_gstack.verify_sha256"), \
                 patch("scripts.prepare_gstack.run_bun_installer", side_effect=RuntimeError("install failed")):
                with self.assertRaisesRegex(RuntimeError, "install failed"):
                    prepare(ROOT, "full", True, {"PATH": ""})
            self.assertFalse(installer.exists())

    def test_bun_rediscovery_uses_supplied_home(self) -> None:
        observed_paths: list[str] = []
        def find(env: dict[str, str]) -> Path | None:
            observed_paths.append(env.get("PATH", ""))
            return None if len(observed_paths) == 1 else Path("/fake/bun")
        with tempfile.TemporaryDirectory() as directory, \
             patch("scripts.prepare_gstack.find_bun", side_effect=find), \
             patch("scripts.prepare_gstack.download_installer", return_value=Path(directory) / "bun-install"), \
             patch("scripts.prepare_gstack.verify_sha256"), \
             patch("scripts.prepare_gstack.run_bun_installer"), \
             patch("scripts.prepare_gstack.subprocess.run"):
            prepare(ROOT, "full", True, {"PATH": "/original", "HOME": directory})
        self.assertTrue(observed_paths[1].startswith(f"{Path(directory) / '.bun/bin'}{os.pathsep}"))
if __name__ == "__main__":
    unittest.main()

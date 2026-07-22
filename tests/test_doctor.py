import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.install_gstack import desired_links


ROOT = Path(__file__).resolve().parents[1]


class DoctorTests(unittest.TestCase):
    def test_launches_pinned_codebase_memory_package_with_closed_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory) / "bin"
            fake_bin.mkdir()
            npx_log = Path(directory) / "npx.log"

            for command in ("codex", "node", "python3"):
                path = fake_bin / command
                path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)

            npx = fake_bin / "npx"
            npx.write_text(
                "#!/usr/bin/env bash\n"
                'printf "%s\\n" "$*" >> "$NPX_LOG"\n'
                "if IFS= read -r _; then exit 97; fi\n",
                encoding="utf-8",
            )
            npx.chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "doctor.sh")],
                env={
                    **os.environ,
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                    "PYTHON": str(fake_bin / "python3"),
                    "NPX_LOG": str(npx_log),
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(npx_log.exists(), "doctor did not invoke npx")
            self.assertEqual(
                npx_log.read_text(encoding="utf-8"),
                "-y codebase-memory-mcp@0.8.1\n",
            )

    def run_doctor(self, home: Path) -> subprocess.CompletedProcess[str]:
        import sys

        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory) / "bin"
            fake_bin.mkdir()
            for command in ("codex", "node"):
                path = fake_bin / command
                path.write_text("#!/usr/bin/env bash\\nexit 0\\n", encoding="utf-8")
                path.chmod(0o755)
            python = fake_bin / "python3"
            python.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1" = "-c" ]; then exec "$REAL_PYTHON" "$@"; fi\n'
                "exit 0\n",
                encoding="utf-8",
            )
            python.chmod(0o755)
            npx = fake_bin / "npx"
            npx.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            npx.chmod(0o755)
            return subprocess.run(
                ["bash", str(ROOT / "scripts" / "doctor.sh")],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                    "PYTHON": str(python),
                    "REAL_PYTHON": sys.executable,
                },
                capture_output=True,
                text=True,
            )
    def write_gstack_state(self, home: Path, mode: str) -> tuple[dict[Path, Path], Path]:
        links = desired_links(ROOT, home, mode)
        for target, source in links.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=source.is_dir())
        state = home / ".codex" / "gstack-managed.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps(
                {
                    "version": 1,
                    "mode": mode,
                    "links": {str(target): str(source) for target, source in links.items()},
                }
            ),
            encoding="utf-8",
        )
        return links, state

    def test_reports_installed_gstack_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            self.write_gstack_state(home, "workflow")
            result = self.run_doctor(home)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok      gstack workflow", result.stdout)


    def test_reports_complete_gstack_full_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            self.write_gstack_state(home, "full")
            result = self.run_doctor(home)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok      gstack full", result.stdout)
    def test_reports_managed_gstack_off_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            self.write_gstack_state(home, "off")
            result = self.run_doctor(home)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok      gstack off", result.stdout)

    def test_rejects_broken_gstack_state_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            state = home / ".codex" / "gstack-managed.json"
            state.parent.mkdir(parents=True)
            state.symlink_to(home / "missing-state")
            result = self.run_doctor(home)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gstack managed state invalid", result.stderr)

    def test_rejects_incomplete_full_gstack_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            state = home / ".codex" / "gstack-managed.json"
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({"version": 1, "mode": "full", "links": {}}), encoding="utf-8")
            result = self.run_doctor(home)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gstack managed link mismatch", result.stderr)

    def test_rejects_workflow_link_with_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            target = home / ".codex" / "skills" / "gstack-office-hours"
            missing_source = home / "missing-source"
            target.parent.mkdir(parents=True)
            target.symlink_to(missing_source, target_is_directory=True)
            state = home / ".codex" / "gstack-managed.json"
            state.write_text(
                json.dumps({"version": 1, "mode": "workflow", "links": {str(target): str(missing_source)}}),
                encoding="utf-8",
            )
            result = self.run_doctor(home)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gstack managed link mismatch", result.stderr)

    def test_rejects_gstack_managed_link_to_wrong_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            links, _ = self.write_gstack_state(home, "workflow")
            target = next(iter(links))
            wrong_source = home / "wrong-source"
            wrong_source.mkdir()
            target.unlink()
            target.symlink_to(wrong_source, target_is_directory=True)
            result = self.run_doctor(home)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gstack managed link mismatch", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gstack managed link mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()

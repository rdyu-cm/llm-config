import os
import subprocess
import tempfile
import unittest
from pathlib import Path


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

    def write_gstack_state(self, home: Path, source: Path, target: Path) -> None:
        import json

        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=True)
        state = home / ".codex" / "gstack-managed.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps({"version": 1, "mode": "workflow", "links": {str(target): str(source)}}),
            encoding="utf-8",
        )

    def test_reports_installed_gstack_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            source = Path(directory) / "source"
            target = home / ".codex" / "skills" / "gstack-office-hours"
            source.mkdir()
            self.write_gstack_state(home, source, target)
            result = self.run_doctor(home)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok      gstack workflow", result.stdout)

    def test_rejects_gstack_managed_link_to_wrong_source(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            source = Path(directory) / "source"
            wrong_source = Path(directory) / "wrong-source"
            target = home / ".codex" / "skills" / "gstack-office-hours"
            source.mkdir()
            wrong_source.mkdir()
            self.write_gstack_state(home, wrong_source, target)
            (home / ".codex" / "gstack-managed.json").write_text(
                json.dumps({"version": 1, "mode": "workflow", "links": {str(target): str(source)}}),
                encoding="utf-8",
            )
            result = self.run_doctor(home)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gstack managed link mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()

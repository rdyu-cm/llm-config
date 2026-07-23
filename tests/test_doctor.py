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

if __name__ == "__main__":
    unittest.main()

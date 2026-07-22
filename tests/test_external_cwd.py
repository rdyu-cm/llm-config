import os
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExternalWorkingDirectoryTests(unittest.TestCase):
    def test_contract_suite_is_importable_outside_repository(self):
        if os.environ.get("CODEX_CONFIG_NESTED_TEST") == "1":
            return

        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory) / "bin"
            fake_bin.mkdir()
            for command in ("codex", "node", "npx"):
                executable = fake_bin / command
                executable.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                executable.chmod(0o755)
            python = fake_bin / "python3"
            python.write_text(
                "#!/usr/bin/env bash\nexec \"$REAL_PYTHON\" \"$@\"\n",
                encoding="utf-8",
            )
            python.chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "doctor.sh")],
                cwd=tempfile.gettempdir(),
                env={
                    **os.environ,
                    "CODEX_CONFIG_NESTED_TEST": "1",
                    "HOME": directory,
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                    "PYTHON": str(python),
                    "REAL_PYTHON": sys.executable,
                },
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Ran ", result.stdout + result.stderr)
        self.assertIn("ok      hook contract tests", result.stdout)


if __name__ == "__main__":
    unittest.main()

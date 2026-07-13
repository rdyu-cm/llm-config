import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExternalWorkingDirectoryTests(unittest.TestCase):
    def test_contract_suite_is_importable_outside_repository(self):
        if os.environ.get("CODEX_CONFIG_NESTED_TEST") == "1":
            return

        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "doctor.sh")],
                cwd=tempfile.gettempdir(),
                env={
                    **os.environ,
                    "CODEX_CONFIG_NESTED_TEST": "1",
                    "HOME": directory,
                    "PYTHON": sys.executable,
                },
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

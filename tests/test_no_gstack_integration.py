import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "docs/superpowers/plans/2026-07-23-lean-skill-catalog.md",
    "docs/superpowers/specs/2026-07-23-lean-skill-catalog-design.md",
    "scripts/bootstrap.ps1",
    "scripts/bootstrap.sh",
    "scripts/cleanup_legacy_gstack.py",
    "tests/test_bootstrap.py",
    "tests/test_capability_bundle.py",
    "tests/test_cleanup_legacy_gstack.py",
    "tests/test_no_gstack_integration.py",
}
RETIRED_TERMS = ("gstack", "gbrain", "garry", "yc office")


class NoGstackIntegrationTests(unittest.TestCase):
    def test_only_bounded_migration_and_history_docs_reference_gstack(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        violations: list[str] = []
        for relative in result.stdout.splitlines():
            if relative in ALLOWED:
                continue
            lowered_path = relative.lower()
            if any(term in lowered_path for term in RETIRED_TERMS):
                violations.append(relative)
                continue
            path = ROOT / relative
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
            except UnicodeDecodeError:
                continue
            if any(term in text for term in RETIRED_TERMS):
                violations.append(relative)

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()

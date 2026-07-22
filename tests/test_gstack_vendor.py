import tomllib
import unittest
from pathlib import Path

from scripts.validate import validate_gstack_vendor


ROOT = Path(__file__).resolve().parents[1]
PIN = "a3259400a366593e0c909dd9ac3e59752efd2488"


class GstackVendorTests(unittest.TestCase):
    def test_lock_and_vendor_identify_exact_upstream_revision(self) -> None:
        with (ROOT / "sources.lock.toml").open("rb") as handle:
            lock = tomllib.load(handle)
        source = next(item for item in lock["sources"] if item["name"] == "gstack")
        with (ROOT / "vendor/gstack-source.toml").open("rb") as handle:
            metadata = tomllib.load(handle)

        self.assertEqual(source["repository"], "https://github.com/garrytan/gstack")
        self.assertEqual(source["commit"], PIN)
        self.assertEqual(source["license"], "MIT (vendor/gstack/LICENSE)")
        validate_gstack_vendor(ROOT, lock)
        self.assertEqual(metadata["commit"], PIN)

    def test_vendor_does_not_contain_nested_git_metadata(self) -> None:
        self.assertFalse((ROOT / "vendor" / "gstack" / ".git").exists())

    def test_validator_requires_global_discover_entrypoint(self) -> None:
        with (ROOT / "sources.lock.toml").open("rb") as handle:
            lock = tomllib.load(handle)
        entrypoint = ROOT / "vendor/gstack/bin/gstack-global-discover.ts"
        missing_entrypoint = entrypoint.with_suffix(".missing")
        entrypoint.rename(missing_entrypoint)
        try:
            with self.assertRaisesRegex(ValueError, "gstack-global-discover.ts"):
                validate_gstack_vendor(ROOT, lock)
        finally:
            missing_entrypoint.rename(entrypoint)


if __name__ == "__main__":
    unittest.main()

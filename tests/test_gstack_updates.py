#!/usr/bin/env python3
"""Tests for the throttled gstack update notice."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.gstack_updates import check_update


ROOT = Path(__file__).resolve().parents[1]


class GstackUpdateTests(unittest.TestCase):
    def test_reports_changed_remote_head_and_caches_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            notice = check_update(
                ROOT / "sources.lock.toml",
                cache,
                True,
                remote_head="84be2f97c4190000000000000000000000000000",
            )
            self.assertIn("update  gstack:", notice)
            self.assertEqual(json.loads(cache.read_text())["head"][:12], "84be2f97c419")

    def test_fresh_cache_avoids_remote_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            cache.write_text(json.dumps({"checked_at": 4102444800, "head": "84be2f97c419"}))
            notice = check_update(ROOT / "sources.lock.toml", cache, False)
            self.assertIn("84be2f97c419", notice)

    def test_network_failure_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            self.assertIsNone(check_update(ROOT / "sources.lock.toml", cache, True, remote_head=""))

    def test_malformed_cache_is_treated_as_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            cache.write_text("[]")
            self.assertIsNone(check_update(ROOT / "sources.lock.toml", cache, False, remote_head=""))

    def test_missing_gstack_lock_entry_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "sources.lock.toml"
            lock.write_text("version = 1\n")
            self.assertIsNone(check_update(lock, Path(directory) / "update.json", True, remote_head=""))


if __name__ == "__main__":
    unittest.main()

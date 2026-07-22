#!/usr/bin/env python3
"""Tests for the throttled gstack update notice."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.gstack_updates import CACHE_VERSION, cache_path, check_update, write_cache


ROOT = Path(__file__).resolve().parents[1]
PINNED = "a3259400a366593e0c909dd9ac3e59752efd2488"
REMOTE = "84be2f97c4190000000000000000000000000000"


class GstackUpdateTests(unittest.TestCase):
    def test_reports_changed_remote_head_and_caches_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            notice = check_update(
                ROOT / "sources.lock.toml",
                cache,
                True,
                remote_head=REMOTE,
            )
            self.assertIn("update  gstack:", notice)
            self.assertEqual(json.loads(cache.read_text())["head"][:12], "84be2f97c419")

    def test_fresh_cache_avoids_remote_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            cache.write_text(
                json.dumps(
                    {"version": CACHE_VERSION, "checked_at": 4102444800, "pinned": PINNED, "head": REMOTE}
                )
            )
            notice = check_update(ROOT / "sources.lock.toml", cache, False)
            self.assertIn(REMOTE[:12], notice)

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

    def test_timeout_is_cached_to_throttle_offline_probes(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.gstack_updates.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git"], 2),
        ) as run:
            cache = Path(directory) / "update.json"
            self.assertIsNone(check_update(ROOT / "sources.lock.toml", cache, False))
            self.assertIsNone(check_update(ROOT / "sources.lock.toml", cache, False))

            self.assertEqual(run.call_count, 1)
            self.assertIsNone(json.loads(cache.read_text())["head"])

    def test_invalid_remote_head_is_cached_to_throttle_offline_probes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            self.assertIsNone(check_update(ROOT / "sources.lock.toml", cache, False, remote_head="invalid"))
            self.assertIsNone(check_update(ROOT / "sources.lock.toml", cache, False, remote_head="invalid"))

            self.assertIsNone(json.loads(cache.read_text())["head"])

    def test_cache_is_reprobed_when_pinned_commit_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "sources.lock.toml"
            cache = Path(directory) / "update.json"
            old_pinned = "1111111111111111111111111111111111111111"
            new_pinned = "2222222222222222222222222222222222222222"
            lock.write_text(
                f'[[sources]]\nname = "gstack"\nrepository = "https://example.invalid/gstack"\ncommit = "{old_pinned}"\n'
            )
            check_update(lock, cache, True, remote_head=REMOTE)
            lock.write_text(
                f'[[sources]]\nname = "gstack"\nrepository = "https://example.invalid/gstack"\ncommit = "{new_pinned}"\n'
            )

            notice = check_update(lock, cache, False, remote_head="3333333333333333333333333333333333333333")

            self.assertIn("222222222222 -> 333333333333", notice)
            self.assertEqual(json.loads(cache.read_text())["pinned"], new_pinned)

    def test_cache_is_reprobed_when_schema_version_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            cache.write_text(
                json.dumps({"version": 0, "checked_at": 4102444800, "pinned": PINNED, "head": REMOTE})
            )

            check_update(ROOT / "sources.lock.toml", cache, False, remote_head="3333333333333333333333333333333333333333")

            self.assertEqual(json.loads(cache.read_text())["version"], CACHE_VERSION)
            self.assertEqual(json.loads(cache.read_text())["head"], "3333333333333333333333333333333333333333")

    def test_cache_writes_use_unique_temporary_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.gstack_updates.os.replace", wraps=os.replace
        ) as replace:
            cache = Path(directory) / "update.json"
            write_cache(cache, PINNED, REMOTE)
            write_cache(cache, PINNED, REMOTE)

            self.assertNotEqual(replace.call_args_list[0].args[0], replace.call_args_list[1].args[0])

    def test_concurrent_cache_writes_leave_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            threads = [threading.Thread(target=write_cache, args=(cache, PINNED, REMOTE)) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(json.loads(cache.read_text())["head"], REMOTE)

    def test_empty_or_relative_xdg_cache_home_falls_back_to_home_cache(self) -> None:
        with patch.dict(os.environ, {"XDG_CACHE_HOME": ""}):
            self.assertEqual(cache_path(), Path.home() / ".cache" / "codex-config" / "gstack-update.json")
        with patch.dict(os.environ, {"XDG_CACHE_HOME": "relative-cache"}):
            self.assertEqual(cache_path(), Path.home() / ".cache" / "codex-config" / "gstack-update.json")


if __name__ == "__main__":
    unittest.main()

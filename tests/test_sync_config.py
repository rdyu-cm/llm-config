import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.sync_config import is_current, merge, render, runtime_overlay


class SyncConfigTests(unittest.TestCase):
    def test_portable_values_win_recursively(self):
        local = {"model": "local", "mcp_servers": {"docs": {"enabled": False}}}
        portable = {"sandbox_mode": "workspace-write", "mcp_servers": {"docs": {"enabled": True}}}

        result = merge(local, portable)

        self.assertEqual(result["model"], "local")
        self.assertTrue(result["mcp_servers"]["docs"]["enabled"])

    def test_render_round_trips_machine_paths(self):
        config = {
            "model": "gpt-example",
            "projects": {"/home/example/project": {"trust_level": "trusted"}},
            "agents": {"max_threads": 4},
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(render(config), encoding="utf-8")
            with path.open("rb") as handle:
                self.assertEqual(tomllib.load(handle), config)

    def test_runtime_overlay_keeps_only_hook_trust_state(self):
        config = {
            "hooks": {"state": {"example": {"trusted_hash": "sha256:test"}}},
            "model": "runtime-model",
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(render(config), encoding="utf-8")

            self.assertEqual(runtime_overlay(path), {"hooks": config["hooks"]})

    def test_current_check_ignores_toml_formatting(self):
        expected = {"model": "example", "hooks": {"state": {"entry": {"trusted_hash": "sha256:test"}}}}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '# Codex may reformat this file\nmodel="example"\n[hooks.state.entry]\ntrusted_hash = "sha256:test"\n',
                encoding="utf-8",
            )

            self.assertTrue(is_current(path, expected))


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from scripts.cleanup_legacy_gstack import cleanup


class CleanupLegacyGstackTests(unittest.TestCase):
    def make_home(self, directory: str) -> Path:
        home = Path(directory) / "home"
        (home / ".codex").mkdir(parents=True)
        return home

    def write_state(self, home: Path, links: dict[Path, Path], **overrides: object) -> Path:
        payload: dict[str, object] = {
            "version": 1,
            "mode": "full",
            "links": {str(target): str(source) for target, source in links.items()},
        }
        payload.update(overrides)
        state = home / ".codex/gstack-managed.json"
        state.write_text(json.dumps(payload), encoding="utf-8")
        return state

    def test_absent_state_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            self.assertEqual(cleanup(home, apply=True), [])

    def test_dry_run_reports_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            source = home / "source"
            source.mkdir()
            target = home / ".codex/skills/gstack-example"
            target.parent.mkdir()
            target.symlink_to(source, target_is_directory=True)
            state = self.write_state(home, {target: source})

            messages = cleanup(home, apply=False)

            self.assertEqual(messages, [f"would   remove {target}", f"would   remove {state}"])
            self.assertTrue(target.is_symlink())
            self.assertTrue(state.exists())

    def test_apply_removes_exact_recorded_links_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            source = home / "source"
            source.mkdir()
            target = home / ".codex/skills/gstack-example"
            target.parent.mkdir()
            target.symlink_to(source, target_is_directory=True)
            state = self.write_state(home, {target: source})

            messages = cleanup(home, apply=True)

            self.assertEqual(messages, [f"removed {target}", f"removed {state}"])
            self.assertFalse(target.is_symlink())
            self.assertFalse(state.exists())

    def test_regular_target_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            target = home / ".codex/skills/gstack-example"
            target.parent.mkdir()
            target.write_text("mine", encoding="utf-8")
            state = self.write_state(home, {target: home / "source"})

            with self.assertRaisesRegex(ValueError, "legacy cleanup conflict"):
                cleanup(home, apply=True)

            self.assertEqual(target.read_text(encoding="utf-8"), "mine")
            self.assertTrue(state.exists())

    def test_changed_symlink_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            target = home / ".codex/skills/gstack-example"
            target.parent.mkdir()
            target.symlink_to(home / "user-source", target_is_directory=True)
            state = self.write_state(home, {target: home / "recorded-source"})

            with self.assertRaisesRegex(ValueError, "legacy cleanup conflict"):
                cleanup(home, apply=True)

            self.assertEqual(target.readlink(), home / "user-source")
            self.assertTrue(state.exists())

    def test_malformed_or_invalid_state_is_rejected(self) -> None:
        invalid_payloads: tuple[object, ...] = (
            [],
            {"version": 2, "links": {}},
            {"version": 1, "links": []},
            {"version": 1, "links": {"/target": 1}},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                home = self.make_home(directory)
                state = home / ".codex/gstack-managed.json"
                state.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "invalid legacy managed state"):
                    cleanup(home, apply=True)

                self.assertTrue(state.exists())

        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            state = home / ".codex/gstack-managed.json"
            state.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid legacy managed state"):
                cleanup(home, apply=True)

    def test_symlinked_state_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            payload = home / "payload.json"
            payload.write_text('{"version": 1, "links": {}}', encoding="utf-8")
            state = home / ".codex/gstack-managed.json"
            state.symlink_to(payload)

            with self.assertRaisesRegex(ValueError, "invalid legacy managed state"):
                cleanup(home, apply=True)

            self.assertTrue(state.is_symlink())

    def test_target_outside_home_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            outside = Path(directory) / "outside"
            state = self.write_state(home, {outside: home / "source"})

            with self.assertRaisesRegex(ValueError, "outside home"):
                cleanup(home, apply=True)

            self.assertTrue(state.exists())

    def test_preflight_prevents_partial_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_home(directory)
            source = home / "source"
            source.mkdir()
            safe = home / ".codex/skills/gstack-safe"
            conflict = home / ".codex/skills/gstack-conflict"
            safe.parent.mkdir()
            safe.symlink_to(source, target_is_directory=True)
            conflict.write_text("mine", encoding="utf-8")
            state = self.write_state(home, {safe: source, conflict: source})

            with self.assertRaisesRegex(ValueError, "legacy cleanup conflict"):
                cleanup(home, apply=True)

            self.assertTrue(safe.is_symlink())
            self.assertTrue(conflict.exists())
            self.assertTrue(state.exists())


if __name__ == "__main__":
    unittest.main()

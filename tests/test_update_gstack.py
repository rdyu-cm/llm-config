import io
import shutil
import os
import subprocess
import tarfile
import tempfile
from contextlib import redirect_stderr
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.update_gstack import (
    extract_archive,
    prepare_update,
    replace_directory,
    update_lock_commit,
    validate_candidate,
    write_codex_metadata,
)


CANDIDATE = "0123456789abcdef0123456789abcdef01234567"


def add_file(handle: tarfile.TarFile, name: str, content: bytes = b"x") -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    handle.addfile(info, io.BytesIO(content))


def write_archive(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as handle:
        for name, content in members.items():
            add_file(handle, name, content)


class UpdateGstackTests(unittest.TestCase):
    def test_rejects_non_commit_candidate(self) -> None:
        for candidate in ("main", CANDIDATE.upper(), "a" * 39, "a" * 41):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "40 hexadecimal"):
                    validate_candidate(candidate)

    def test_extract_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            archive = temporary / "bad.tar.gz"
            write_archive(archive, {"gstack-abc/../../escape": b"x"})
            with self.assertRaisesRegex(ValueError, "unsafe archive path"):
                extract_archive(archive, temporary / "out")
            self.assertFalse((temporary / "escape").exists())

    def test_extract_rejects_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            archive = temporary / "bad.tar.gz"
            write_archive(archive, {"/tmp/gstack-escape": b"x"})
            with self.assertRaisesRegex(ValueError, "unsafe archive path"):
                extract_archive(archive, temporary / "out")

    def test_extract_rejects_windows_paths(self) -> None:
        for name in (r"gstack-abc\..\escape", r"C:\escape", "C:/escape"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                archive = temporary / "bad.tar.gz"
                write_archive(archive, {name: b"x"})
                with self.assertRaisesRegex(ValueError, "unsafe archive path"):
                    extract_archive(archive, temporary / "out")

    def test_extract_rejects_links_and_devices(self) -> None:
        cases = ((tarfile.SYMTYPE, "link"), (tarfile.LNKTYPE, "link"), (tarfile.CHRTYPE, "device"), (tarfile.FIFOTYPE, "device"))
        for member_type, error in cases:
            with self.subTest(member_type=member_type), tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                archive = temporary / "bad.tar.gz"
                with tarfile.open(archive, "w:gz") as handle:
                    info = tarfile.TarInfo("gstack-abc/bad")
                    info.type = member_type
                    info.linkname = "../outside"
                    handle.addfile(info)
                with self.assertRaisesRegex(ValueError, error):
                    extract_archive(archive, temporary / "out")

    def test_extract_rejects_ambiguous_archive_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            archive = temporary / "bad.tar.gz"
            write_archive(archive, {"gstack-one/LICENSE": b"one", "gstack-two/LICENSE": b"two"})
            with self.assertRaisesRegex(ValueError, "exactly one root"):
                extract_archive(archive, temporary / "out")

    def test_extract_returns_the_single_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            archive = temporary / "good.tar.gz"
            write_archive(archive, {"gstack-abc/LICENSE": b"license", "gstack-abc/hosts/codex.ts": b"host"})
            extracted = extract_archive(archive, temporary / "out")
            self.assertEqual(extracted, temporary / "out" / "gstack-abc")
            self.assertEqual((extracted / "LICENSE").read_bytes(), b"license")

    def test_update_lock_changes_only_gstack_commit_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "sources.lock.toml"
            original = (
                'version = 1\n\n[[sources]]\nname = "other"\ncommit = "111"\n\n'
                '[[sources]]\nname = "gstack"\nrepository = "https://github.com/garrytan/gstack"\n'
                'commit = "old" # pinned\nitems = ["vendor"]\n'
            )
            lock.write_text(original, encoding="utf-8")
            update_lock_commit(lock, CANDIDATE)
            expected = original.replace('commit = "old" # pinned', f'commit = "{CANDIDATE}" # pinned')
            self.assertEqual(lock.read_text(encoding="utf-8"), expected)

    def test_update_lock_preserves_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "sources.lock.toml"
            original = b'[[sources]]\r\nname = "gstack"\r\ncommit = "old"\r\n'
            lock.write_bytes(original)
            update_lock_commit(lock, CANDIDATE)
            self.assertEqual(lock.read_bytes(), original.replace(b'"old"', f'"{CANDIDATE}"'.encode()))

    def test_invalid_archive_does_not_create_repository_parents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "candidate.tar.gz"
            write_archive(archive, {"gstack-candidate/LICENSE": b"only one file"})
            with patch("scripts.update_gstack._ensure_targets_clean"):
                with self.assertRaisesRegex(ValueError, "missing setup"):
                    prepare_update(root, CANDIDATE, archive)
            self.assertFalse((root / "vendor").exists())
            self.assertFalse((root / "generated").exists())

    def test_codex_metadata_is_normalized_to_repository_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "openai.yaml"
            metadata.write_text("raw upstream metadata\n", encoding="utf-8")
            write_codex_metadata(metadata, "gstack-review")
            self.assertEqual(
                metadata.read_text(encoding="utf-8"),
                'interface:\n'
                '  display_name: "gstack-review"\n'
                '  short_description: "Use the $gstack-review workflow."\n'
                '  default_prompt: "Invoke $gstack-review for this task."\n'
                'policy:\n'
                '  allow_implicit_invocation: true\n',
            )

    def test_replace_directory_restores_old_tree_when_install_rename_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            staged = temporary / "staged"
            target = temporary / "target"
            staged.mkdir()
            target.mkdir()
            (staged / "marker").write_text("new", encoding="utf-8")
            (target / "marker").write_text("old", encoding="utf-8")
            real_replace = os.replace
            calls = 0

            def fail_second_replace(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated rename failure")
                real_replace(source, destination)

            with patch("scripts.update_gstack.os.replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(OSError, "simulated"):
                    replace_directory(staged, target)
            self.assertEqual((target / "marker").read_text(encoding="utf-8"), "old")
            self.assertEqual((staged / "marker").read_text(encoding="utf-8"), "new")

    def test_prepare_update_stages_generation_and_leaves_only_reviewable_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive)

            def generate(_root: Path, staged_vendor: Path, staged_generated: Path) -> None:
                self.assertEqual((staged_vendor / "LICENSE").read_text(encoding="utf-8"), "new license")
                for name in ("gstack-test", "gstack-upgrade"):
                    skill = staged_generated / name
                    (skill / "agents").mkdir(parents=True)
                    (skill / "SKILL.md").write_text(
                        f"---\nname: {name}\ndescription: test skill description\n---\nbody\n",
                        encoding="utf-8",
                    )
                    (skill / "agents/openai.yaml").write_text(
                        f'interface:\n  display_name: "{name}"\n'
                        f'  short_description: "Use the ${name} workflow."\n'
                        f'  default_prompt: "Invoke ${name} for this task."\n'
                        'policy:\n  allow_implicit_invocation: true\n',
                        encoding="utf-8",
                    )

            with patch("scripts.update_gstack.generate_codex_skills", side_effect=generate):
                prepare_update(root, CANDIDATE, archive)

            status = subprocess.check_output(
                ["git", "status", "--short", "--untracked-files=all"], cwd=root, text=True
            ).splitlines()
            changed = {line[3:] for line in status}
            changed.remove("candidate.tar.gz")
            self.assertEqual(
                changed,
                {
                    "generated/gstack-codex/gstack-test/SKILL.md",
                    "generated/gstack-codex/gstack-test/agents/openai.yaml",
                    "generated/gstack-codex/gstack-upgrade/SKILL.md",
                    "generated/gstack-codex/gstack-upgrade/agents/openai.yaml",
                    "sources.lock.toml",
                    "vendor/gstack-source.toml",
                    "vendor/gstack/LICENSE",
                    "vendor/gstack/hosts/codex.ts",
                    "vendor/gstack/package.json",
                    "vendor/gstack/setup",
                },
            )
            self.assertEqual((root / "vendor/gstack/LICENSE").read_text(encoding="utf-8"), "new license")
            self.assertIn(CANDIDATE, (root / "sources.lock.toml").read_text(encoding="utf-8"))
            self.assertIn(CANDIDATE, (root / "vendor/gstack-source.toml").read_text(encoding="utf-8"))

    def test_second_replacement_failure_restores_both_repository_trees(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive)
            real_replace = replace_directory
            calls = 0

            def fail_second_replacement(staged: Path, target: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("second replacement failed")
                real_replace(staged, target)

            def generate(_root: Path, _staged_vendor: Path, staged_generated: Path) -> None:
                for name in ("gstack-test", "gstack-upgrade"):
                    skill = staged_generated / name
                    (skill / "agents").mkdir(parents=True)
                    (skill / "SKILL.md").write_text(
                        f"---\nname: {name}\ndescription: test skill description\n---\nbody\n",
                        encoding="utf-8",
                    )
                    (skill / "agents/openai.yaml").write_text(
                        f'interface:\n  display_name: "{name}"\n'
                        f'  short_description: "Use the ${name} workflow."\n'
                        f'  default_prompt: "Invoke ${name} for this task."\n'
                        'policy:\n  allow_implicit_invocation: true\n',
                        encoding="utf-8",
                    )

            with patch("scripts.update_gstack.generate_codex_skills", side_effect=generate), \
                 patch("scripts.update_gstack.replace_directory", side_effect=fail_second_replacement):
                with self.assertRaisesRegex(OSError, "second replacement"):
                    prepare_update(root, CANDIDATE, archive)

            self.assertEqual((root / "vendor/gstack/LICENSE").read_text(encoding="utf-8"), "old license")
            self.assertEqual(
                (root / "generated/gstack-codex/gstack-test/SKILL.md").read_text(encoding="utf-8"),
                "old skill",
            )
            self.assertIn('commit = "old"', (root / "sources.lock.toml").read_text(encoding="utf-8"))
            self.assertIn('commit = "old"', (root / "vendor/gstack-source.toml").read_text(encoding="utf-8"))

    def test_metadata_failure_rolls_back_lock_and_both_trees(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive)
            with patch("scripts.update_gstack.generate_codex_skills", side_effect=self._write_generated_fixture), \
                 patch("scripts.update_gstack.write_source_metadata", side_effect=OSError("metadata failed")):
                with self.assertRaisesRegex(OSError, "metadata failed"):
                    prepare_update(root, CANDIDATE, archive)
            self.assertEqual((root / "vendor/gstack/LICENSE").read_text(encoding="utf-8"), "old license")
            self.assertIn('commit = "old"', (root / "sources.lock.toml").read_text(encoding="utf-8"))

    def test_backup_cleanup_failure_does_not_report_update_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive)
            real_rmtree = shutil.rmtree

            def fail_backup_cleanup(path: Path, *args, **kwargs) -> None:
                if ".transaction-" in Path(path).name:
                    raise OSError("cleanup failed")
                real_rmtree(path, *args, **kwargs)

            errors = io.StringIO()
            with redirect_stderr(errors), \
                 patch("scripts.update_gstack.generate_codex_skills", side_effect=self._write_generated_fixture), \
                 patch("scripts.update_gstack.shutil.rmtree", side_effect=fail_backup_cleanup):
                prepare_update(root, CANDIDATE, archive)
            self.assertEqual((root / "vendor/gstack/LICENSE").read_text(encoding="utf-8"), "new license")

    def test_generation_failure_preserves_existing_repository_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive)
            before = subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=root, text=True)
            with patch("scripts.update_gstack.generate_codex_skills", side_effect=RuntimeError("generator failed")):
                with self.assertRaisesRegex(RuntimeError, "generator failed"):
                    prepare_update(root, CANDIDATE, archive)
            after = subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=root, text=True)
            self.assertEqual(after, before)
            self.assertEqual((root / "vendor/gstack/LICENSE").read_text(encoding="utf-8"), "old license")

    def _make_valid_archive(self, archive: Path) -> None:
        write_archive(
            archive,
            {
                "gstack-candidate/LICENSE": b"new license",
                "gstack-candidate/setup": b"#!/bin/sh\n",
                "gstack-candidate/package.json": b"{}\n",
                "gstack-candidate/hosts/codex.ts": b"export default {};\n",
            },
        )

    def _write_generated_fixture(self, _root: Path, _vendor: Path, generated: Path) -> None:
        for name in ("gstack-test", "gstack-upgrade"):
            skill = generated / name
            (skill / "agents").mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: test skill description\n---\nbody\n", encoding="utf-8"
            )
            (skill / "agents/openai.yaml").write_text(
                f'interface:\n  display_name: "{name}"\n'
                f'  short_description: "Use the ${name} workflow."\n'
                f'  default_prompt: "Invoke ${name} for this task."\n'
                'policy:\n  allow_implicit_invocation: true\n', encoding="utf-8"
            )

    def _make_repository(self, root: Path) -> None:
        (root / "vendor/gstack/hosts").mkdir(parents=True)
        (root / "generated/gstack-codex/gstack-test/agents").mkdir(parents=True)
        (root / "vendor/gstack/LICENSE").write_text("old license", encoding="utf-8")
        (root / "vendor/gstack/setup").write_text("old setup", encoding="utf-8")
        (root / "vendor/gstack/package.json").write_text("old package", encoding="utf-8")
        (root / "vendor/gstack/hosts/codex.ts").write_text("old host", encoding="utf-8")
        (root / "vendor/gstack-source.toml").write_text(
            'repository = "https://github.com/garrytan/gstack"\ncommit = "old"\n', encoding="utf-8"
        )
        (root / "generated/gstack-codex/gstack-test/SKILL.md").write_text("old skill", encoding="utf-8")
        (root / "generated/gstack-codex/gstack-test/agents/openai.yaml").write_text("old metadata", encoding="utf-8")
        (root / "gstack-capabilities.toml").write_text(
            'version = 1\n[profiles.workflow]\nskills = ["gstack-test"]\n'
            '[profiles.full]\nskills = ["gstack-test"]\n',
            encoding="utf-8",
        )
        (root / "sources.lock.toml").write_text(
            'version = 1\n\n[[sources]]\nname = "other"\ncommit = "other"\n\n'
            '[[sources]]\nname = "gstack"\nrepository = "https://github.com/garrytan/gstack"\ncommit = "old"\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
            cwd=root,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()

import io
import shutil
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib
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

ROOT = Path(__file__).resolve().parents[1]

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
    def test_bounded_update_paths_include_both_generated_bundles(self) -> None:
        from scripts.update_gstack import UPDATE_PATHS

        self.assertIn("generated/gstack-codex", UPDATE_PATHS)
        self.assertIn("generated/gstack-codex-workflow", UPDATE_PATHS)

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

    def test_download_archive_uses_exact_candidate_url(self) -> None:
        from scripts.update_gstack import download_archive

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "candidate.tar.gz"
            response = io.BytesIO(b"candidate archive")
            with patch("scripts.update_gstack.urllib.request.urlopen", return_value=response) as urlopen:
                download_archive(CANDIDATE, destination)

            urlopen.assert_called_once_with(
                f"https://github.com/garrytan/gstack/archive/{CANDIDATE}.tar.gz",
                timeout=30,
            )
            self.assertEqual(destination.read_bytes(), b"candidate archive")

    def test_prepare_update_rejects_archive_root_for_different_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive, root_name=f"gstack-{'f' * 40}")

            with patch("scripts.update_gstack.generate_codex_skills") as generate:
                with self.assertRaisesRegex(ValueError, "archive root.*candidate"):
                    prepare_update(root, CANDIDATE, archive)

            generate.assert_not_called()
            self._assert_update_targets_old(root)

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
            write_archive(archive, {f"gstack-{CANDIDATE}/LICENSE": b"only one file"})
            with patch("scripts.update_gstack._ensure_targets_clean"):
                with self.assertRaisesRegex(ValueError, "missing setup"):
                    prepare_update(root, CANDIDATE, archive)
            self.assertFalse((root / "vendor").exists())
            self.assertFalse((root / "generated").exists())
    def test_trusted_adapter_matches_current_generated_tree_byte_for_byte(self) -> None:
        from scripts.update_gstack import generate_codex_skills

        with tempfile.TemporaryDirectory() as directory:
            for profile, root_name, expected_count in (
                ("full", "gstack-codex", 106),
                ("workflow", "gstack-codex-workflow", 56),
            ):
                generated = Path(directory) / root_name
                generated.mkdir()
                generate_codex_skills(
                    ROOT, ROOT / "vendor/gstack", generated, profile
                )
                expected = ROOT / "generated" / root_name
                actual_files = sorted(
                    path.relative_to(generated)
                    for path in generated.rglob("*")
                    if path.is_file()
                )
                expected_files = sorted(
                    path.relative_to(expected)
                    for path in expected.rglob("*")
                    if path.is_file()
                )
                self.assertEqual(len(actual_files), expected_count, profile)
                self.assertEqual(actual_files, expected_files, profile)
                for relative in expected_files:
                    self.assertEqual(
                        (generated / relative).read_bytes(),
                        (expected / relative).read_bytes(),
                        f"{profile}: {relative}",
                    )


    def test_changed_candidate_skill_keeps_codex_adapter_invariants(self) -> None:
        from scripts.update_gstack import generate_codex_skills

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            candidate = temporary / "candidate"
            generated = temporary / "generated"
            (candidate / "review").mkdir(parents=True)
            generated.mkdir()
            source = (ROOT / "vendor/gstack/review/SKILL.md").read_text(encoding="utf-8")
            source = source.replace(
                "Pre-landing PR review. (gstack)",
                "Pre-landing PR review with candidate fidelity. (gstack)",
                1,
            )
            source = source.replace(
                "## When to invoke this skill",
                'Literal generator examples: `${{ github.ref }}` and `{{"status":"ok"}}`.\n\n'
                "## When to invoke this skill",
                1,
            )
            (candidate / "review/SKILL.md").write_text(source, encoding="utf-8")

            generate_codex_skills(ROOT, candidate, generated)

            adapted = (generated / "gstack-review/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("candidate fidelity", adapted)
            self.assertIn("Analyzes diff against the base branch", adapted.split("---", 2)[1])
            self.assertIn('GSTACK_ROOT="$HOME/.codex/skills/gstack"', adapted)
            self.assertIn('GSTACK_BIN="$GSTACK_ROOT/bin"', adapted)
            self.assertNotIn(".claude/skills", adapted)
            self.assertNotIn("Review Army — Specialist Dispatch", adapted)
            self.assertNotIn("Adversarial review (always-on)", adapted)
            self.assertIn("${{ github.ref }}", adapted)
            self.assertIn('{{"status":"ok"}}', adapted)

            from scripts.update_gstack import _validate_generated_tree

            _validate_generated_tree(ROOT, generated)

    def test_adapter_normalizes_and_initializes_runtime_paths(self) -> None:
        from scripts.update_gstack import _adapt_codex_skill

        source = (
            "---\nname: test\ndescription: Runtime path fixture. (gstack)\n---\n"
            "## Preamble (run first)\n\n```bash\n"
            'B="$HOME$GSTACK_BROWSE/browse"\n'
            'D="$HOME$GSTACK_DESIGN/design"\n'
            'P="$HOME$GSTACK_MAKE_PDF/pdf"\n'
            "```\n"
        )

        adapted = _adapt_codex_skill(source, "gstack-test")

        self.assertNotIn("$HOME$GSTACK_", adapted)
        self.assertIn('GSTACK_BROWSE="$GSTACK_ROOT/browse/dist"', adapted)
        self.assertIn('GSTACK_DESIGN="$GSTACK_ROOT/design/dist"', adapted)
        self.assertIn('GSTACK_MAKE_PDF="$GSTACK_ROOT/make-pdf"', adapted)
        self.assertIn('B="$GSTACK_BROWSE/browse"', adapted)
        self.assertIn('D="$GSTACK_DESIGN/design"', adapted)
        self.assertIn('P="$GSTACK_MAKE_PDF/pdf"', adapted)

    def test_adapter_rewrites_workflow_browser_fallbacks(self) -> None:
        from scripts.update_gstack import _adapt_codex_skill, _apply_workflow_safe_fallbacks

        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            workflow = tomllib.load(handle)["profiles"]["workflow"]["skills"]
        from tests.test_gstack_catalog import workflow_browser_policy_violations

        violations = {}
        for name in workflow:
            relative = name.removeprefix("gstack-")
            source = (ROOT / "vendor/gstack" / relative / "SKILL.md").read_text(
                encoding="utf-8"
            )
            adapted = _adapt_codex_skill(source, name, workflow_safe=True)
            found = workflow_browser_policy_violations(adapted)
            if found:
                violations[name] = found
        self.assertEqual(violations, {})

        office_hours = _adapt_codex_skill(
            (ROOT / "vendor/gstack/office-hours/SKILL.md").read_text(encoding="utf-8"),
            "gstack-office-hours",
            workflow_safe=True,
        )
        plan_design = _adapt_codex_skill(
            (ROOT / "vendor/gstack/plan-design-review/SKILL.md").read_text(encoding="utf-8"),
            "gstack-plan-design-review",
            workflow_safe=True,
        )

        self.assertNotIn("NEEDS_SETUP", office_hours)
        self.assertNotIn("bun.sh/install", office_hours)
        self.assertNotIn("Run the setup script to enable it.", office_hours)
        self.assertIn("Skip browser preview and setup", office_hours)
        self.assertIn("report the saved artifact path", office_hours)
        self.assertNotIn("file://", office_hours)
        self.assertIn("Report the HTML artifact path", office_hours)

        self.assertNotIn("--serve", plan_design)
        self.assertIn("save the comparison board HTML", plan_design)
        self.assertIn("report its artifact path", plan_design)
        self.assertIn("continue the non-browser review flow", plan_design)

        ship = _apply_workflow_safe_fallbacks(
            (ROOT / "generated/gstack-codex/gstack-ship/SKILL.md").read_text(
                encoding="utf-8"
            ),
            "gstack-ship",
        )
        self.assertNotRegex(ship, r"(?<![A-Za-z0-9_-])/qa(?:-only)?\b")
        self.assertNotIn("browse-based verification", ship)
        self.assertNotIn("screenshot evidence", ship)
        self.assertIn("Run the existing automated verification commands", ship)
        self.assertIn("Do not launch a browser", ship)

    def test_generation_never_executes_candidate_package_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            generated = root / "staged-generated"
            fake_bin = root / "bin"
            sentinel = root / "outside-sentinel"
            (candidate / "test").mkdir(parents=True)
            (candidate / "gstack-upgrade").mkdir()
            generated.mkdir()
            fake_bin.mkdir()
            (root / "generated/gstack-codex/gstack-test").mkdir(parents=True)
            (root / "generated/gstack-codex/gstack-upgrade").mkdir()
            (root / "gstack-capabilities.toml").write_text(
                'version = 1\n[bun]\nversion = "1.3.10"\n'
                '[profiles.workflow]\ngenerated_root = "generated/gstack-codex-workflow"\n'
                'skills = ["gstack-test"]\n[profiles.full]\n'
                'generated_root = "generated/gstack-codex"\nskills = ["gstack-test"]\n',
                encoding="utf-8",
            )
            for relative, name in (("test", "test"), ("gstack-upgrade", "gstack-upgrade")):
                (candidate / relative / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: Candidate data only.\n---\n"
                    "Use ~/.claude/skills/gstack/bin safely.\n",
                    encoding="utf-8",
                )
            (candidate / "package.json").write_text(
                '{"scripts":{"gen:skill-docs":"touch $SENTINEL_PATH"}}\n',
                encoding="utf-8",
            )
            fake_bun = fake_bin / "bun"
            fake_bun.write_text(
                '#!/bin/sh\n: > "$SENTINEL_PATH"\nprintf "1.3.10\\n"\n',
                encoding="utf-8",
            )
            fake_bun.chmod(0o755)

            from scripts.update_gstack import generate_codex_skills

            with patch.dict(
                os.environ,
                {"PATH": str(fake_bin), "SENTINEL_PATH": str(sentinel)},
            ):
                generate_codex_skills(root, candidate, generated)

            self.assertFalse(sentinel.exists())
            adapted = (generated / "gstack-test/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("name: gstack-test", adapted)
            self.assertIn("$GSTACK_ROOT/bin", adapted)

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

    def test_staged_validator_rejects_claude_paths_and_missing_initialization(self) -> None:
        from scripts.update_gstack import _validate_generated_tree

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / "staged"
            (root / "generated/gstack-codex/gstack-test").mkdir(parents=True)
            (root / "gstack-capabilities.toml").write_text(
                'version = 1\n[profiles.full]\ngenerated_root = "generated/gstack-codex"\n'
                'skills = ["gstack-test"]\n', encoding="utf-8"
            )
            (root / "generated/gstack-codex/gstack-test/SKILL.md").write_text(
                "GSTACK_ROOT=x\nGSTACK_BIN=x\n", encoding="utf-8"
            )
            self._write_generated_fixture(root, root / "vendor", staged)
            skill = staged / "gstack-test/SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + ".claude/skills/bad\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Claude path"):
                _validate_generated_tree(root, staged)

            skill.write_text(
                "---\nname: gstack-test\ndescription: test\n---\n"
                "GSTACK_ROOT=x\nGSTACK_BIN=x\nGSTACK_BROWSE=x\n"
                'B="$HOME$GSTACK_BROWSE/browse"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "doubled home prefix"):
                _validate_generated_tree(root, staged)

            skill.write_text(
                "---\nname: gstack-test\ndescription: test\n---\n"
                "GSTACK_ROOT=x\nGSTACK_BIN=x\n"
                'B="$GSTACK_BROWSE/browse"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "GSTACK_BROWSE.*without initialization"):
                _validate_generated_tree(root, staged)

            skill.write_text(
                "---\nname: gstack-test\ndescription: test\n---\nbody\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "GSTACK_ROOT"):
                _validate_generated_tree(root, staged)

    def test_staged_validator_accepts_full_known_good_golden_tree(self) -> None:
        from scripts.update_gstack import _validate_generated_tree

        _validate_generated_tree(ROOT, ROOT / "generated/gstack-codex")

    def test_staged_validator_rejects_generator_placeholder_token(self) -> None:
        from scripts.update_gstack import _validate_generated_tree

        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "gstack-codex"
            shutil.copytree(ROOT / "generated/gstack-codex", generated)
            skill = generated / "gstack-review/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\n{{PREAMBLE}}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unresolved template"):
                _validate_generated_tree(ROOT, generated)

    def test_staged_validator_rejects_workflow_browser_setup_fallbacks(self) -> None:
        from scripts.update_gstack import _validate_generated_tree

        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "gstack-codex-workflow"
            shutil.copytree(ROOT / "generated/gstack-codex-workflow", generated)
            office_hours = generated / "gstack-office-hours/SKILL.md"
            office_hours.write_text(
                office_hours.read_text(encoding="utf-8") + "\nNEEDS_SETUP\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "browser setup fallback"):
                _validate_generated_tree(ROOT, generated, "workflow")

            shutil.copy(
                ROOT / "generated/gstack-codex-workflow/gstack-office-hours/SKILL.md",
                office_hours,
            )
            plan_design = generated / "gstack-plan-design-review/SKILL.md"
            plan_design.write_text(
                plan_design.read_text(encoding="utf-8") + "\nopen file://artifact.html\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "system browser fallback"):
                _validate_generated_tree(ROOT, generated, "workflow")

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

    def test_candidate_added_skill_requires_catalog_review_before_repo_touch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive, extra_skills=("surprise",))

            with patch("scripts.update_gstack.generate_codex_skills") as generate:
                with self.assertRaisesRegex(ValueError, "review required.*added: gstack-surprise"):
                    prepare_update(root, CANDIDATE, archive)

            generate.assert_not_called()
            self._assert_update_targets_old(root)

    def test_candidate_removed_skill_requires_catalog_review_before_repo_touch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive, skills=("gstack-upgrade",))

            with patch("scripts.update_gstack.generate_codex_skills") as generate:
                with self.assertRaisesRegex(ValueError, "review required.*removed: gstack-test"):
                    prepare_update(root, CANDIDATE, archive)

            generate.assert_not_called()
            self._assert_update_targets_old(root)

    def test_trusted_gate_runs_only_fixed_repository_validator(self) -> None:
        from scripts.update_gstack import _run_trusted_integration_gate, write_source_metadata

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            (root / "scripts").mkdir()
            validator = root / "scripts/validate.py"
            validator.write_text("trusted validator fixture\n", encoding="utf-8")
            update_lock_commit(root / "sources.lock.toml", CANDIDATE)
            write_source_metadata(root / "vendor/gstack-source.toml", CANDIDATE)
            self._write_generated_fixture(root, root / "vendor/gstack", root / "generated/gstack-codex")
            self._write_generated_fixture(
                root,
                root / "vendor/gstack",
                root / "generated/gstack-codex-workflow",
                "workflow",
            )
            completed = subprocess.CompletedProcess([], 0, stdout="validated\n")

            with patch("scripts.update_gstack.subprocess.run", return_value=completed) as run:
                _run_trusted_integration_gate(root, CANDIDATE)

            run.assert_called_once_with(
                [sys.executable, str(validator)],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

    def test_trusted_gate_failure_rolls_back_all_four_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive)

            with patch(
                "scripts.update_gstack.generate_codex_skills",
                side_effect=self._write_generated_fixture,
            ), patch(
                "scripts.update_gstack._run_trusted_integration_gate",
                side_effect=RuntimeError("trusted integration gate failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "trusted integration gate failed"):
                    prepare_update(root, CANDIDATE, archive)

            self._assert_update_targets_old(root)

    def test_prepare_update_stages_generation_and_leaves_only_reviewable_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            archive = root / "candidate.tar.gz"
            self._make_valid_archive(archive)

            def generate(
                _root: Path, staged_vendor: Path, staged_generated: Path, profile: str
            ) -> None:
                self.assertEqual((staged_vendor / "LICENSE").read_text(encoding="utf-8"), "new license")
                names = ("gstack-test", "gstack-upgrade") if profile == "full" else ("gstack-test",)
                for name in names:
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

            def gate(gate_root: Path, candidate: str) -> None:
                self.assertEqual(gate_root, root)
                self.assertEqual(candidate, CANDIDATE)
                self.assertEqual((root / "vendor/gstack/LICENSE").read_text(), "new license")
                self.assertIn("test skill description", (root / "generated/gstack-codex/gstack-test/SKILL.md").read_text())
                self.assertIn(CANDIDATE, (root / "sources.lock.toml").read_text())
                self.assertIn(CANDIDATE, (root / "vendor/gstack-source.toml").read_text())

            with patch("scripts.update_gstack.generate_codex_skills", side_effect=generate), patch(
                "scripts.update_gstack._run_trusted_integration_gate", side_effect=gate
            ):
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
                    "generated/gstack-codex-workflow/gstack-test/SKILL.md",
                    "generated/gstack-codex-workflow/gstack-test/agents/openai.yaml",
                    "sources.lock.toml",
                    "vendor/gstack-source.toml",
                    "vendor/gstack/LICENSE",
                    "vendor/gstack/hosts/codex.ts",
                    "vendor/gstack/package.json",
                    "vendor/gstack/setup",
                    "vendor/gstack/test/SKILL.md.tmpl",
                    "vendor/gstack/gstack-upgrade/SKILL.md.tmpl",
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

            def generate(
                _root: Path, _staged_vendor: Path, staged_generated: Path, profile: str
            ) -> None:
                names = ("gstack-test", "gstack-upgrade") if profile == "full" else ("gstack-test",)
                for name in names:
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
                 patch("scripts.update_gstack.shutil.rmtree", side_effect=fail_backup_cleanup), \
                 patch("scripts.update_gstack._run_trusted_integration_gate"):
                prepare_update(root, CANDIDATE, archive)
            self.assertEqual((root / "vendor/gstack/LICENSE").read_text(encoding="utf-8"), "new license")
            self.assertIn("backup cleanup failed", errors.getvalue())
            self.assertIn(".transaction-", errors.getvalue())

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

    def _make_valid_archive(
        self,
        archive: Path,
        *,
        root_name: str | None = None,
        skills: tuple[str, ...] = ("test", "gstack-upgrade"),
        extra_skills: tuple[str, ...] = (),
    ) -> None:
        root_name = root_name or f"gstack-{CANDIDATE}"
        members = {
            f"{root_name}/LICENSE": b"new license",
            f"{root_name}/setup": b"#!/bin/sh\n",
            f"{root_name}/package.json": b"{}\n",
            f"{root_name}/hosts/codex.ts": b"export default {};\n",
        }
        for skill in (*skills, *extra_skills):
            members[f"{root_name}/{skill}/SKILL.md.tmpl"] = b"canonical skill template\n"
        write_archive(archive, members)

    def _assert_update_targets_old(self, root: Path) -> None:
        self.assertEqual((root / "vendor/gstack/LICENSE").read_text(), "old license")
        self.assertFalse((root / "vendor/gstack/test").exists())
        self.assertEqual(
            (root / "generated/gstack-codex/gstack-test/SKILL.md").read_text(),
            "old skill",
        )
        self.assertFalse((root / "generated/gstack-codex/gstack-upgrade").exists())
        self.assertEqual(
            (root / "generated/gstack-codex-workflow/gstack-test/SKILL.md").read_text(),
            "old workflow skill",
        )
        self.assertIn('commit = "old"', (root / "sources.lock.toml").read_text())
        self.assertIn('commit = "old"', (root / "vendor/gstack-source.toml").read_text())

    def _write_generated_fixture(
        self, _root: Path, _vendor: Path, generated: Path, profile: str = "full"
    ) -> None:
        names = ("gstack-test", "gstack-upgrade") if profile == "full" else ("gstack-test",)
        for name in names:
            skill = generated / name
            (skill / "agents").mkdir(parents=True, exist_ok=True)
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
        (root / "generated/gstack-codex-workflow/gstack-test/agents").mkdir(parents=True)
        (root / "vendor/gstack/LICENSE").write_text("old license", encoding="utf-8")
        (root / "vendor/gstack/setup").write_text("old setup", encoding="utf-8")
        (root / "vendor/gstack/package.json").write_text("old package", encoding="utf-8")
        (root / "vendor/gstack/hosts/codex.ts").write_text("old host", encoding="utf-8")
        (root / "vendor/gstack-source.toml").write_text(
            'repository = "https://github.com/garrytan/gstack"\ncommit = "old"\n', encoding="utf-8"
        )
        (root / "generated/gstack-codex/gstack-test/SKILL.md").write_text("old skill", encoding="utf-8")
        (root / "generated/gstack-codex/gstack-test/agents/openai.yaml").write_text("old metadata", encoding="utf-8")
        (root / "generated/gstack-codex-workflow/gstack-test/SKILL.md").write_text(
            "old workflow skill", encoding="utf-8"
        )
        (root / "generated/gstack-codex-workflow/gstack-test/agents/openai.yaml").write_text(
            "old workflow metadata", encoding="utf-8"
        )
        (root / "gstack-capabilities.toml").write_text(
            'version = 1\n[profiles.workflow]\n'
            'generated_root = "generated/gstack-codex-workflow"\nskills = ["gstack-test"]\n'
            '[profiles.full]\ngenerated_root = "generated/gstack-codex"\n'
            'skills = ["gstack-test"]\n',
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

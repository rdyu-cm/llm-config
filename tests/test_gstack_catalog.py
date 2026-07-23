import tomllib
import shutil
import tempfile
import re
from scripts.validate import (
    find_workflow_browser_policy_violations,
    parse_gstack_openai_metadata,
    validate_gstack_catalog,
)

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER_SKILLS = {
    "gstack-benchmark", "gstack-browse", "gstack-canary", "gstack-design-consultation",
    "gstack-design-review", "gstack-design-shotgun", "gstack-devex-review", "gstack-diagram",
    "gstack-ios-clean", "gstack-ios-design-review", "gstack-ios-fix", "gstack-ios-qa",
    "gstack-ios-sync", "gstack-land-and-deploy", "gstack-make-pdf", "gstack-open-gstack-browser",
    "gstack-pair-agent", "gstack-qa", "gstack-qa-only", "gstack-scrape",
    "gstack-setup-browser-cookies", "gstack-skillify",
}
RUNTIME_SKILLS = {
    "GSTACK_BROWSE": {
        "gstack-benchmark", "gstack-browse", "gstack-canary", "gstack-design-consultation",
        "gstack-design-html", "gstack-design-review", "gstack-design-shotgun",
        "gstack-devex-review", "gstack-land-and-deploy",
        "gstack-office-hours", "gstack-open-gstack-browser", "gstack-pair-agent",
        "gstack-plan-design-review",
        "gstack-qa", "gstack-qa-only", "gstack-setup-browser-cookies",
    },
    "GSTACK_DESIGN": {
        "gstack-design-consultation", "gstack-design-html", "gstack-design-review",
        "gstack-design-shotgun", "gstack-office-hours", "gstack-plan-design-review",
    },
    "GSTACK_MAKE_PDF": {"gstack-make-pdf"},
}


def workflow_browser_policy_violations(text: str) -> list[str]:
    violations: list[str] = []
    launch_command = re.compile(
        r"(?i)(?:^|`)\s*(?:xdg-open\s+\S+|open\s+"
        r"(?:(?:https?|file)://|[\"'$~/.]|URL\d*\b|\S+\.(?:html?|pdf|png)))"
    )
    platform_start = re.compile(
        r"(?i)(?:^|`)\s*start(?:\s+\"[^\"]*\")?\s+"
        r"(?:(?:https?|file)://|[\"'$~/.])"
    )
    setup_guidance = re.compile(
        r"(?i)\$D setup|cd <SKILL_DIR> && \./setup|bun\.sh/install|"
        r"install (?:bun|browser)|(?:browse|browser|designer|visual mockup)"
        r"[^.\n]{0,80}(?:needs? (?:a )?(?:build|setup)|(?:isn't|is not) set up)"
    )
    positive_browser_wording = re.compile(
        r"(?i)\b(?:default|your) browser\b|\b(?:then|and) open it\b|"
        r"\b(?:board|browser tab)\b[^.\n]{0,60}\b(?:open|opened)\b"
    )
    open_authorization = re.compile(r"(?i)`open`\s+(?:for|\(fallback|is allowed)|fallback for viewing boards")
    for line_number, line in enumerate(text.splitlines(), 1):
        reasons: list[str] = []
        if launch_command.search(line) or re.search(r"(?i)run\s+`(?:open|xdg-open)`", line):
            reasons.append("launch command")
        if platform_start.search(line):
            reasons.append("platform start command")
        if "file://" in line:
            reasons.append("file URL")
        if "--serve" in line or re.search(r"\$D\s+serve\b", line):
            reasons.append("browser-serving command")
        if setup_guidance.search(line):
            reasons.append("setup guidance")
        if open_authorization.search(line):
            reasons.append("open authorization")
        negative_browser_absence = re.search(
            r"(?i)\b(?:do not|don't|never|without|skip|not available|non-browser)\b", line
        )
        if positive_browser_wording.search(line) and not negative_browser_absence:
            reasons.append("browser-launch wording")
        violations.extend(f"line {line_number}: {reason}" for reason in reasons)
    return violations


class GstackCatalogTests(unittest.TestCase):
    def test_generated_runtime_paths_are_initialized_and_resolved(self) -> None:
        generated = ROOT / "generated/gstack-codex"
        texts = {
            path.parent.name: path.read_text(encoding="utf-8")
            for path in generated.glob("gstack-*/SKILL.md")
        }
        for name, text in texts.items():
            self.assertNotIn("$HOME$GSTACK_", text, name)

        for variable, expected_skills in RUNTIME_SKILLS.items():
            used_by = {
                name
                for name, text in texts.items()
                if re.search(rf"\$(?:\{{)?{variable}(?:\}})?", text)
            }
            self.assertEqual(used_by, expected_skills, variable)
            for name in expected_skills:
                self.assertRegex(texts[name], rf"(?m)^{variable}=", name)

    def test_workflow_catalog_has_no_browser_launch_or_setup_guidance(self) -> None:
        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            workflow = tomllib.load(handle)["profiles"]["workflow"]["skills"]
        self.assertEqual(len(workflow), 28)

        violations = {}
        for name in workflow:
            text = (ROOT / "generated/gstack-codex-workflow" / name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            found = workflow_browser_policy_violations(text)
            found.extend(find_workflow_browser_policy_violations(text))
            if found:
                violations[name] = found
        self.assertEqual(violations, {})

    def test_workflow_policy_rejects_only_browser_qa_routing_contexts(self) -> None:
        unsafe = (
            "Invoke /qa or /qa-only for site behavior.\n"
            "Before browse-based verification, probe the dev server.\n"
            "Show failures with screenshot evidence.\n"
        )
        violations = find_workflow_browser_policy_violations(unsafe)
        self.assertTrue(any("browser-only skill routing" in item for item in violations))
        self.assertTrue(any("browser verification" in item for item in violations))

        safe = (
            "Run quality assurance tests and inspect the browse command's logs.\n"
            "Archive existing screenshots as evidence without launching a browser.\n"
        )
        self.assertEqual(find_workflow_browser_policy_violations(safe), [])

    def test_workflow_browser_policy_allows_browser_absence_prose(self) -> None:
        safe = (
            "If the runtime is not available, skip the preview and continue the non-browser "
            "workflow. Do not invoke a system browser; report the saved artifact path."
        )
        self.assertEqual(workflow_browser_policy_violations(safe), [])

    def test_catalog_validator_rejects_workflow_browser_launch_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            shutil.copy(ROOT / "gstack-capabilities.toml", temporary_root / "gstack-capabilities.toml")
            shutil.copytree(ROOT / "generated", temporary_root / "generated")
            skill = temporary_root / "generated/gstack-codex-workflow/gstack-review/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\n```bash\nxdg-open artifact.html\n```\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "browser launch policy.*gstack-review"):
                validate_gstack_catalog(temporary_root)

    def test_workflow_catalog_excludes_browser_capabilities(self) -> None:
        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        workflow = set(catalog["profiles"]["workflow"]["skills"])
        self.assertTrue({"gstack-office-hours", "gstack-plan-eng-review", "gstack-review", "gstack-ship"} <= workflow)
        self.assertFalse(workflow & BROWSER_SKILLS)
        self.assertNotIn("gstack-upgrade", workflow)
    def test_every_generated_sidecar_meets_codex_metadata_contract(self) -> None:
        roots = {"gstack-codex": 53, "gstack-codex-workflow": 28}
        for generated_root, expected_count in roots.items():
            sidecars = sorted(
                (ROOT / "generated" / generated_root).glob("gstack-*/agents/openai.yaml")
            )
            self.assertEqual(len(sidecars), expected_count, generated_root)
            for path in sidecars:
                name = path.parents[1].name
                metadata = parse_gstack_openai_metadata(path)
                self.assertEqual(metadata["interface"]["display_name"], name)
                self.assertGreaterEqual(len(metadata["interface"]["short_description"]), 25)
                self.assertLessEqual(len(metadata["interface"]["short_description"]), 64)
                self.assertIn(f"${name}", metadata["interface"]["default_prompt"])

    def test_shared_skills_split_browser_behavior_by_profile(self) -> None:
        full = ROOT / "generated/gstack-codex"
        workflow = ROOT / "generated/gstack-codex-workflow"
        cases = {
            "gstack-office-hours": ("file://", "Skip browser preview and setup"),
            "gstack-plan-design-review": ("$D compare", "continue the non-browser review flow"),
        }
        for name, (full_branch, workflow_fallback) in cases.items():
            full_text = (full / name / "SKILL.md").read_text(encoding="utf-8")
            workflow_text = (workflow / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(full_branch, full_text, name)
            self.assertIn(workflow_fallback, workflow_text, name)
            self.assertEqual(workflow_browser_policy_violations(workflow_text), [], name)

    def test_ship_splits_browser_qa_from_non_browser_verification(self) -> None:
        full = (ROOT / "generated/gstack-codex/gstack-ship/SKILL.md").read_text(
            encoding="utf-8"
        )
        workflow = (
            ROOT / "generated/gstack-codex-workflow/gstack-ship/SKILL.md"
        ).read_text(encoding="utf-8")

        for browser_branch in ("/qa-only", "browse-based verification", "screenshot evidence"):
            self.assertIn(browser_branch, full)
            self.assertNotIn(browser_branch, workflow)
        self.assertIn("Run the existing automated verification commands", workflow)
        self.assertIn("Do not launch a browser", workflow)

    def test_catalog_rejects_gstack_upgrade_in_full_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            shutil.copy(ROOT / "gstack-capabilities.toml", temporary_root / "gstack-capabilities.toml")
            (temporary_root / "generated").mkdir()
            (temporary_root / "generated" / "gstack-codex").symlink_to(
                ROOT / "generated" / "gstack-codex", target_is_directory=True
            )
            catalog = (temporary_root / "gstack-capabilities.toml").read_text(encoding="utf-8")
            catalog = catalog.rsplit('  "gstack-unfreeze",\n]', 1)[0] + '  "gstack-unfreeze",\n  "gstack-upgrade",\n]\n'
            (temporary_root / "gstack-capabilities.toml").write_text(catalog, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "gstack-upgrade"):
                validate_gstack_catalog(temporary_root)

    def test_catalog_requires_upgrade_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            shutil.copy(ROOT / "gstack-capabilities.toml", temporary_root / "gstack-capabilities.toml")
            shutil.copytree(ROOT / "generated", temporary_root / "generated")
            shutil.rmtree(temporary_root / "generated/gstack-codex/gstack-upgrade")
            with self.assertRaisesRegex(ValueError, "missing generated gstack skill: gstack-upgrade"):
                validate_gstack_catalog(temporary_root)



    def test_every_catalog_skill_has_generated_codex_frontmatter(self) -> None:
        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        for name in catalog["profiles"]["full"]["skills"]:
            text = (ROOT / "generated" / "gstack-codex" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"name: {name}", text)
            self.assertIn("description:", text)

    def test_global_policy_preserves_model_aware_roles(self) -> None:
        policy = (ROOT / "AGENTS.global.md").read_text(encoding="utf-8")
        self.assertIn("## Gstack subagent routing", policy)
        self.assertIn("implementer_standard", policy)
        self.assertIn("security_reviewer", policy)
        self.assertIn("preserve the upstream subtask prompt verbatim", policy)
        self.assertIn("## Planning skill routing", policy)
        self.assertIn("material product, architecture, interface, or behavior choices", policy)
        self.assertIn("not required for diagnostics, mechanical edits", policy)
        self.assertIn("not automatic merely because a plan exists", policy)
        self.assertIn("## Worktree-first changes", policy)
        self.assertIn("explicit approval before merging", policy)


if __name__ == "__main__":
    unittest.main()

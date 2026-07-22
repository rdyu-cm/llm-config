import tomllib
import shutil
import tempfile
import re
from scripts.validate import parse_gstack_openai_metadata, validate_gstack_catalog

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
        "gstack-devex-review", "gstack-land-and-deploy", "gstack-office-hours",
        "gstack-open-gstack-browser", "gstack-pair-agent", "gstack-plan-design-review",
        "gstack-qa", "gstack-qa-only", "gstack-setup-browser-cookies",
    },
    "GSTACK_DESIGN": {
        "gstack-design-consultation", "gstack-design-html", "gstack-design-review",
        "gstack-design-shotgun", "gstack-office-hours", "gstack-plan-design-review",
    },
    "GSTACK_MAKE_PDF": {"gstack-make-pdf"},
}


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

    def test_workflow_skills_skip_optional_browser_setup_and_system_open(self) -> None:
        generated = ROOT / "generated/gstack-codex"
        office_hours = (generated / "gstack-office-hours/SKILL.md").read_text(encoding="utf-8")
        plan_design = (generated / "gstack-plan-design-review/SKILL.md").read_text(
            encoding="utf-8"
        )

        for name, text in (
            ("gstack-office-hours", office_hours),
            ("gstack-plan-design-review", plan_design),
        ):
            for forbidden in (
                "NEEDS_SETUP",
                "cd <SKILL_DIR> && ./setup",
                "bun.sh/install",
                "Run the setup script to enable it.",
                "open file://",
            ):
                self.assertNotIn(forbidden, text, name)
        self.assertIn("skip browser preview and setup", office_hours)
        self.assertIn("report the saved artifact path", office_hours)
        self.assertIn('$B goto "file://$SKETCH_FILE"', office_hours)

        self.assertIn("save the comparison board HTML", plan_design)
        self.assertIn("report its artifact path", plan_design)
        self.assertIn("continue the non-browser review flow", plan_design)
        self.assertIn("BROWSE_READY: $B", plan_design)

    def test_workflow_catalog_excludes_browser_capabilities(self) -> None:
        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        workflow = set(catalog["profiles"]["workflow"]["skills"])
        self.assertTrue({"gstack-office-hours", "gstack-plan-eng-review", "gstack-review", "gstack-ship"} <= workflow)
        self.assertFalse(workflow & BROWSER_SKILLS)
        self.assertNotIn("gstack-upgrade", workflow)
    def test_every_generated_sidecar_meets_codex_metadata_contract(self) -> None:
        sidecars = sorted((ROOT / "generated" / "gstack-codex").glob("gstack-*/agents/openai.yaml"))
        self.assertEqual(len(sidecars), 53)
        for path in sidecars:
            name = path.parents[1].name
            metadata = parse_gstack_openai_metadata(path)
            self.assertEqual(metadata["interface"]["display_name"], name)
            self.assertGreaterEqual(len(metadata["interface"]["short_description"]), 25)
            self.assertLessEqual(len(metadata["interface"]["short_description"]), 64)
            self.assertIn(f"${name}", metadata["interface"]["default_prompt"])

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
            skills = temporary_root / "generated" / "gstack-codex"
            skills.mkdir(parents=True)
            for source in (ROOT / "generated" / "gstack-codex").glob("gstack-*"):
                if source.name != "gstack-upgrade":
                    (skills / source.name).symlink_to(source, target_is_directory=True)
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


if __name__ == "__main__":
    unittest.main()

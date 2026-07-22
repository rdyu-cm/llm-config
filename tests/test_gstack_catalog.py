import tomllib
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


class GstackCatalogTests(unittest.TestCase):
    def test_workflow_catalog_excludes_browser_capabilities(self) -> None:
        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        workflow = set(catalog["profiles"]["workflow"]["skills"])
        self.assertTrue({"gstack-office-hours", "gstack-plan-eng-review", "gstack-review", "gstack-ship"} <= workflow)
        self.assertFalse(workflow & BROWSER_SKILLS)
        self.assertNotIn("gstack-upgrade", workflow)

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

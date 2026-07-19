import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CapabilityBundleTests(unittest.TestCase):
    def test_codebase_memory_is_enabled_by_default_with_explicit_opt_out_profiles(self):
        with (ROOT / ".codex/config.toml").open("rb") as handle:
            base = tomllib.load(handle)

        self.assertTrue(base["mcp_servers"]["codebase_memory"]["enabled"])
        self.assertEqual(
            base["mcp_servers"]["codebase_memory"]["startup_timeout_sec"],
            60,
        )

        expected = {
            "minimal": False,
            "frontend": False,
            "security": True,
            "full": True,
        }
        for profile, enabled in expected.items():
            with (ROOT / "profiles" / f"{profile}.config.toml").open("rb") as handle:
                config = tomllib.load(handle)
            self.assertEqual(config["mcp_servers"]["codebase_memory"]["enabled"], enabled)

    def test_catalog_paths_exist_and_component_keys_are_unique(self):
        with (ROOT / "capability-bundle.toml").open("rb") as handle:
            catalog = tomllib.load(handle)

        self.assertEqual(catalog["version"], 1)
        self.assertEqual(catalog["workspace_policy"], "one_writer_per_worktree")
        keys = [(item["kind"], item["name"]) for item in catalog["components"]]
        self.assertEqual(len(keys), len(set(keys)))
        for item in catalog["components"]:
            self.assertTrue((ROOT / item["path"]).exists(), item)

    def test_planner_and_implementer_pin_requested_models(self):
        with (ROOT / ".codex/agents/planner.toml").open("rb") as handle:
            planner = tomllib.load(handle)
        with (ROOT / ".codex/agents/implementer.toml").open("rb") as handle:
            implementer = tomllib.load(handle)

        self.assertEqual(planner["model"], "gpt-5.6-sol")
        self.assertEqual(implementer["model"], "gpt-5.6-terra")
        self.assertEqual(planner["sandbox_mode"], "read-only")
        self.assertEqual(implementer["sandbox_mode"], "workspace-write")

    def test_superpowers_tier_agents_pin_models_reasoning_and_sandboxes(self):
        expected = {
            "implementer_fast": ("gpt-5.6-terra", "medium", "workspace-write"),
            "implementer_standard": ("gpt-5.6-sol", "medium", "workspace-write"),
            "implementer_deep": ("gpt-5.6-sol", "high", "workspace-write"),
            "reviewer_standard": ("gpt-5.6-sol", "medium", "read-only"),
            "reviewer_deep": ("gpt-5.6-sol", "high", "read-only"),
        }

        with (ROOT / "capability-bundle.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        catalog_agents = {
            item["name"] for item in catalog["components"] if item["kind"] == "agent"
        }

        for name, (model, effort, sandbox) in expected.items():
            with (ROOT / ".codex" / "agents" / f"{name}.toml").open("rb") as handle:
                agent = tomllib.load(handle)
            self.assertEqual(agent["name"], name)
            self.assertEqual(agent["model"], model)
            self.assertEqual(agent["model_reasoning_effort"], effort)
            self.assertEqual(agent["sandbox_mode"], sandbox)
            self.assertIn("task prompt", agent["developer_instructions"])
            self.assertIn(name, catalog_agents)


if __name__ == "__main__":
    unittest.main()

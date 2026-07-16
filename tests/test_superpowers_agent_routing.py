import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SuperpowersAgentRoutingTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def prompt_hash(self, relative: str) -> str:
        text = self.read(relative)
        body = text.split("  prompt: |\n", 1)[1].split("\n```", 1)[0]
        return hashlib.sha256(body.encode()).hexdigest()

    def test_subagent_driven_development_maps_every_codex_tier(self):
        skill = self.read("skills/subagent-driven-development/SKILL.md")
        for name in (
            "implementer_fast",
            "implementer_standard",
            "implementer_deep",
            "reviewer_standard",
            "reviewer_deep",
        ):
            self.assertIn(f"`{name}`", skill)
        self.assertIn("final whole-branch review", skill)
        self.assertIn("`reviewer_deep`", skill)

    def test_dispatch_templates_select_agents_without_replacing_prompt_contracts(self):
        implementer = self.read(
            "skills/subagent-driven-development/implementer-prompt.md"
        )
        task_reviewer = self.read(
            "skills/subagent-driven-development/task-reviewer-prompt.md"
        )
        final_reviewer = self.read("skills/requesting-code-review/code-reviewer.md")

        self.assertIn("[AGENT]", implementer)
        self.assertIn("implementer_fast", implementer)
        self.assertIn("[AGENT]", task_reviewer)
        self.assertIn("reviewer_standard", task_reviewer)
        self.assertIn("[AGENT]", final_reviewer)
        self.assertIn("reviewer_deep", final_reviewer)
        self.assertEqual(
            self.prompt_hash(
                "skills/subagent-driven-development/implementer-prompt.md"
            ),
            "bf1f525e303c4c37add91883dddd78332d9e957a7d08efaf38645e9b682ff4af",
        )
        self.assertEqual(
            self.prompt_hash(
                "skills/subagent-driven-development/task-reviewer-prompt.md"
            ),
            "3f810ed137cc9dcdc18cbe47450abbc435a1a4f0f5bd1e940222509524274c3d",
        )
        self.assertEqual(
            self.prompt_hash("skills/requesting-code-review/code-reviewer.md"),
            "f170e242028bb747b1235aef4136a2b25fab6a26d42d04678610fad445b0f5f8",
        )

    def test_standalone_review_defaults_standard_and_escalates_deep(self):
        skill = self.read("skills/requesting-code-review/SKILL.md")
        self.assertIn("`reviewer_standard` by default", skill)
        self.assertIn("`reviewer_deep`", skill)


if __name__ == "__main__":
    unittest.main()

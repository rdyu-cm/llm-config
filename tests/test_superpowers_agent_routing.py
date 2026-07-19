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
        for row in (
            "| Complete specification, isolated change, one or two files | "
            "`implementer_fast` | `gpt-5.6-terra`, medium |",
            "| Multi-file integration, pattern matching, or debugging | "
            "`implementer_standard` | `gpt-5.6-terra`, medium |",
            "| Broad architectural context or substantial design judgment | "
            "`implementer_deep` | `gpt-5.6-sol`, high |",
            "| Small or routine task review | `reviewer_standard` | "
            "`gpt-5.6-sol`, medium |",
            "| Subtle, security-sensitive, concurrency-sensitive, or whole-branch "
            "review | `reviewer_deep` | `gpt-5.6-sol`, high |",
        ):
            self.assertIn(row, skill)
        self.assertIn(
            "The final whole-branch review always uses `reviewer_deep`.", skill
        )
        self.assertIn(
            "redispatch once at the next\nstronger implementer tier with the missing "
            "context",
            skill,
        )
        self.assertIn(
            "report it and stop before dispatch rather than silently inheriting the "
            "session\nmodel",
            skill,
        )
        self.assertIn(
            "On non-Codex platforms, keep using a general-purpose subagent with the\n"
            "explicit model selected by the policy above.",
            skill,
        )
        self.assertIn(
            "If it's a context problem, provide more context and re-dispatch with the "
            "same tier",
            skill,
        )
        self.assertIn(
            "If the task requires more reasoning, re-dispatch once at the next stronger "
            "implementer tier",
            skill,
        )

    def test_model_selection_distinguishes_named_and_general_purpose_agents(self):
        skill = self.read("skills/subagent-driven-development/SKILL.md")
        self.assertIn(
            "Named Codex agents get their model and reasoning settings from their TOML "
            "definitions",
            skill,
        )
        self.assertIn(
            "When dispatching a general-purpose subagent, always specify the model "
            "explicitly",
            skill,
        )
        self.assertNotIn(
            "Always specify the model explicitly when dispatching a subagent", skill
        )

    def test_dispatch_templates_select_agents_without_replacing_prompt_contracts(self):
        implementer = self.read(
            "skills/subagent-driven-development/implementer-prompt.md"
        )
        task_reviewer = self.read(
            "skills/subagent-driven-development/task-reviewer-prompt.md"
        )
        final_reviewer = self.read("skills/requesting-code-review/code-reviewer.md")

        self.assertIn(
            "Subagent ([AGENT]):\n"
            '  description: "Implement Task N: [task name]"\n'
            "  model: [MODEL — REQUIRED on platforms without Codex "
            "custom-agent routing;\n"
            "         choose per SKILL.md Model Selection]\n"
            "  prompt: |\n",
            implementer,
        )
        self.assertIn("implementer_fast", implementer)
        self.assertIn(
            "On other platforms, use `general-purpose` and supply `[MODEL]` explicitly.",
            implementer,
        )
        self.assertIn(
            "Subagent ([AGENT]):\n"
            '  description: "Review Task N (spec + quality)"\n'
            "  model: [MODEL — REQUIRED on platforms without Codex "
            "custom-agent routing;\n"
            "         choose per SKILL.md Model Selection]\n"
            "  prompt: |\n",
            task_reviewer,
        )
        self.assertIn("reviewer_standard", task_reviewer)
        self.assertIn(
            "[MODEL]` — REQUIRED on platforms that use `general-purpose` instead of a\n"
            "  named Codex custom agent; choose per SKILL.md Model Selection.",
            task_reviewer,
        )
        self.assertIn(
            "Subagent ([AGENT]):\n"
            '  description: "Review code changes"\n'
            "  model: [MODEL — REQUIRED on platforms without Codex "
            "custom-agent routing]\n"
            "  prompt: |\n",
            final_reviewer,
        )
        self.assertIn("reviewer_deep", final_reviewer)
        self.assertIn(
            "[MODEL]` — REQUIRED on platforms that use `general-purpose` instead of a\n"
            "  named Codex custom agent.",
            final_reviewer,
        )
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
        self.assertIn(
            "On another platform, dispatch a `general-purpose` subagent with an\n"
            "explicit model appropriate to the same risk.",
            skill,
        )

    def test_plan_uses_the_harness_dev_dependency_group(self):
        plan = self.read(
            "docs/superpowers/plans/2026-07-16-superpowers-tiered-agent-routing.md"
        )
        self.assertIn(
            "UV_CACHE_DIR=.uv-cache uv run --group dev pytest "
            "tests/unit/capabilities/test_preflight.py -q",
            plan,
        )
        self.assertIn(
            "The existing harness model-preflight tests pass under the declared "
            "`dev` dependency group",
            plan,
        )
        self.assertNotIn("uv run --extra dev pytest", plan)


if __name__ == "__main__":
    unittest.main()

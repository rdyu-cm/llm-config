# Superpowers Tiered Agent Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route Superpowers implementation and review dispatches through model-pinned Codex custom agents while preserving every task-specific Superpowers prompt.

**Architecture:** Five thin custom-agent TOML layers select fast, standard, or deep model settings. The Superpowers skills retain their existing prompt bodies and choose a named Codex tier at dispatch; non-Codex platforms retain their explicit general-purpose model mechanism. The portable capability catalog admits the agents, while focused static tests prevent routing or prompt-contract regressions.

**Tech Stack:** Codex custom-agent TOML, Markdown skill and prompt templates, Python `unittest`, repository validation scripts.

## Global Constraints

- The complete existing Superpowers implementer and reviewer prompt bodies remain the unchanged source of task-specific requirements, TDD steps, reporting, review criteria, and escalation behavior.
- Custom-agent developer instructions contain only compatible role boundaries and runtime constraints; they do not duplicate the Superpowers workflow.
- `planner.toml` and `implementer.toml` remain unchanged as harness-specific roles.
- Superpowers planning remains in the main thread; do not add a planner subagent.
- Do not add scheduling, subagent lifecycle, event-stream, or persistence behavior to `codex-harness`.
- Pinned models must not silently fall back to another model.
- Do not change Superpowers task decomposition, review loops, report files, or write-isolation rules.

---

### Task 1: Add Portable Tier Agent Definitions

**Files:**
- Create: `.codex/agents/implementer_fast.toml`
- Create: `.codex/agents/implementer_standard.toml`
- Create: `.codex/agents/implementer_deep.toml`
- Create: `.codex/agents/reviewer_standard.toml`
- Create: `.codex/agents/reviewer_deep.toml`
- Modify: `tests/test_capability_bundle.py`
- Modify: `capability-bundle.toml`
- Modify: `README.md`

**Interfaces:**
- Consumes: Codex standalone custom-agent schema (`name`, `description`, `developer_instructions`, plus normal session config keys).
- Produces: named agent types `implementer_fast`, `implementer_standard`, `implementer_deep`, `reviewer_standard`, and `reviewer_deep` for Task 2 routing.

- [ ] **Step 1: Write the failing tier-agent configuration test**

Append this method to `CapabilityBundleTests` in `tests/test_capability_bundle.py`:

```python
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
```

- [ ] **Step 2: Run the focused test and verify it fails because the tier files do not exist**

Run:

```bash
python3 -m unittest tests.test_capability_bundle.CapabilityBundleTests.test_superpowers_tier_agents_pin_models_reasoning_and_sandboxes -v
```

Expected: `ERROR` with `FileNotFoundError` for `.codex/agents/implementer_fast.toml`.

- [ ] **Step 3: Create the three thin implementer agent layers**

Create `.codex/agents/implementer_fast.toml`:

```toml
name = "implementer_fast"
description = "Fast Superpowers implementation worker for mechanical, fully specified changes limited to one or two files."
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"
developer_instructions = '''
Treat the complete task prompt as the task-specific contract. Implement only that bounded task, preserve unrelated changes, run the requested verification, and return the requested report. Do not publish, merge, broaden scope, or introduce a competing workflow.
'''
```

Create `.codex/agents/implementer_standard.toml`:

```toml
name = "implementer_standard"
description = "Standard Superpowers implementation worker for multi-file integration, debugging, and coordination tasks."
model = "gpt-5.6-sol"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"
developer_instructions = '''
Treat the complete task prompt as the task-specific contract. Implement only that bounded task, preserve unrelated changes, run the requested verification, and return the requested report. Do not publish, merge, broaden scope, or introduce a competing workflow.
'''
```

Create `.codex/agents/implementer_deep.toml`:

```toml
name = "implementer_deep"
description = "Deep Superpowers implementation worker for tasks requiring broad context or substantial design judgment."
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
developer_instructions = '''
Treat the complete task prompt as the task-specific contract. Implement only that bounded task, preserve unrelated changes, run the requested verification, and return the requested report. Do not publish, merge, broaden scope, or introduce a competing workflow.
'''
```

- [ ] **Step 4: Create the two thin reviewer agent layers**

Create `.codex/agents/reviewer_standard.toml`:

```toml
name = "reviewer_standard"
description = "Read-only Superpowers reviewer for small or routine task-scoped changes."
model = "gpt-5.6-sol"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = '''
Treat the complete task prompt as the task-specific review rubric. Review only the requested scope, verify claims against evidence, cite concrete files and lines, and return the requested verdict. Do not modify files, Git state, or introduce a competing workflow.
'''
```

Create `.codex/agents/reviewer_deep.toml`:

```toml
name = "reviewer_deep"
description = "Read-only Superpowers reviewer for subtle, high-risk, or whole-branch changes."
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = '''
Treat the complete task prompt as the task-specific review rubric. Review only the requested scope, verify claims against evidence, cite concrete files and lines, and return the requested verdict. Do not modify files, Git state, or introduce a competing workflow.
'''
```

- [ ] **Step 5: Add all five agents to the portable capability catalog**

Insert these entries after the existing `implementer` agent entry in `capability-bundle.toml`:

```toml
[[components]]
name = "implementer_fast"
kind = "agent"
path = ".codex/agents/implementer_fast.toml"
classification = "supported"

[[components]]
name = "implementer_standard"
kind = "agent"
path = ".codex/agents/implementer_standard.toml"
classification = "supported"

[[components]]
name = "implementer_deep"
kind = "agent"
path = ".codex/agents/implementer_deep.toml"
classification = "supported"

[[components]]
name = "reviewer_standard"
kind = "agent"
path = ".codex/agents/reviewer_standard.toml"
classification = "supported"

[[components]]
name = "reviewer_deep"
kind = "agent"
path = ".codex/agents/reviewer_deep.toml"
classification = "supported"
```

- [ ] **Step 6: Update the custom-agent inventory without duplicating the routing rubric**

In `README.md`, replace the stale `.codex/agents/` count in the Layout section with:

```markdown
- `.codex/agents/`: narrow custom agents and Superpowers model tiers.
```

Append this paragraph after the existing explanation of the pinned planner and implementer:

```markdown
Superpowers implementation and review dispatches use five model-tier agents. Fast implementation
uses `implementer_fast`; integration work uses `implementer_standard`; broad design-sensitive work
uses `implementer_deep`; routine review uses `reviewer_standard`; subtle or whole-branch review uses
`reviewer_deep`. Their developer instructions stay intentionally thin so the complete Superpowers
task prompt remains unchanged.
```

- [ ] **Step 7: Run the focused configuration tests and repository validator**

Run:

```bash
python3 -m unittest tests.test_capability_bundle -v
python3 scripts/validate.py
```

Expected: all capability-bundle tests pass, followed by `validated ... 11 agents, 3 hooks, and 4 profiles`.

- [ ] **Step 8: Commit the portable agent definitions**

```bash
git add .codex/agents/implementer_fast.toml .codex/agents/implementer_standard.toml .codex/agents/implementer_deep.toml .codex/agents/reviewer_standard.toml .codex/agents/reviewer_deep.toml tests/test_capability_bundle.py capability-bundle.toml README.md
git commit -m "feat: add Superpowers model-tier agents"
```

---

### Task 2: Route Superpowers Dispatches Through the Tier Agents

**Files:**
- Create: `tests/test_superpowers_agent_routing.py`
- Modify: `skills/subagent-driven-development/SKILL.md`
- Modify: `skills/subagent-driven-development/implementer-prompt.md`
- Modify: `skills/subagent-driven-development/task-reviewer-prompt.md`
- Modify: `skills/requesting-code-review/SKILL.md`
- Modify: `skills/requesting-code-review/code-reviewer.md`

**Interfaces:**
- Consumes: the five named custom agents from Task 1.
- Produces: deterministic Codex routing from existing Superpowers task-complexity signals to a named model tier, while preserving general-purpose explicit-model dispatch on other platforms.

- [ ] **Step 1: Write the failing routing-contract tests**

Create `tests/test_superpowers_agent_routing.py`:

```python
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
```

- [ ] **Step 2: Run the focused routing tests and verify they fail on missing tier names**

Run:

```bash
python3 -m unittest tests.test_superpowers_agent_routing -v
```

Expected: three failing tests because the current skills and templates do not name `[AGENT]` or the Codex tier agents.

- [ ] **Step 3: Add the concrete Codex mapping to the existing model-selection policy**

In `skills/subagent-driven-development/SKILL.md`, insert this subsection immediately after the three task-complexity signal bullets:

```markdown
### Codex Agent Tiers

On Codex, select the named custom agent instead of relying on session-model
inheritance:

| Work | Codex agent | Model and reasoning |
| --- | --- | --- |
| Complete specification, isolated change, one or two files | `implementer_fast` | `gpt-5.6-terra`, medium |
| Multi-file integration, pattern matching, or debugging | `implementer_standard` | `gpt-5.6-sol`, medium |
| Broad architectural context or substantial design judgment | `implementer_deep` | `gpt-5.6-sol`, high |
| Small or routine task review | `reviewer_standard` | `gpt-5.6-sol`, medium |
| Subtle, security-sensitive, concurrency-sensitive, or whole-branch review | `reviewer_deep` | `gpt-5.6-sol`, high |

The final whole-branch review always uses `reviewer_deep`. If an implementer
reports that the task needs more reasoning, redispatch once at the next
stronger implementer tier with the missing context; never repeat the same
underpowered dispatch unchanged. If a required Codex agent is unavailable,
report it and stop before dispatch rather than silently inheriting the session
model. On non-Codex platforms, keep using a general-purpose subagent with the
explicit model selected by the policy above.
```

In the `BLOCKED` handling list, replace items 1 and 2 with:

```markdown
1. If it's a context problem, provide more context and re-dispatch with the same tier
2. If the task requires more reasoning, re-dispatch once at the next stronger implementer tier
```

- [ ] **Step 4: Add a Codex agent placeholder to the implementer wrapper and retain its prompt body**

In `skills/subagent-driven-development/implementer-prompt.md`, replace only the
dispatch wrapper from `Subagent (general-purpose):` through `prompt: |` with:

```text
Subagent ([AGENT]):
  description: "Implement Task N: [task name]"
  model: [MODEL — REQUIRED on platforms without Codex custom-agent routing;
         choose per SKILL.md Model Selection]
  prompt: |
```

Append this placeholder immediately after the dispatch code block's closing
fence:

```markdown
**Dispatch placeholders:**
- `[AGENT]` — REQUIRED on Codex: `implementer_fast`,
  `implementer_standard`, or `implementer_deep` per SKILL.md Model Selection.
  On other platforms, use `general-purpose` and supply `[MODEL]` explicitly.
```

Do not alter any line from `You are implementing Task N` through the end of the existing prompt body.

- [ ] **Step 5: Add the reviewer tier placeholder to the task-review wrapper and retain its rubric**

In `skills/subagent-driven-development/task-reviewer-prompt.md`, replace only
the dispatch wrapper from `Subagent (general-purpose):` through `prompt: |`
with:

```text
Subagent ([AGENT]):
  description: "Review Task N (spec + quality)"
  model: [MODEL — REQUIRED on platforms without Codex custom-agent routing;
         choose per SKILL.md Model Selection]
  prompt: |
```

Add this entry at the start of the existing `Placeholders` list:

```markdown
- `[AGENT]` — REQUIRED on Codex: `reviewer_standard` for a small or routine
  task review, otherwise `reviewer_deep`. On other platforms, use
  `general-purpose` and supply `[MODEL]` explicitly.
```

Do not alter any line from `You are reviewing one task's implementation` through the end of the existing review prompt body.

- [ ] **Step 6: Route standalone and final reviews while retaining the complete review prompt**

In `skills/requesting-code-review/SKILL.md`, replace the sentence beginning `Dispatch a general-purpose subagent` with:

```markdown
On Codex, dispatch `reviewer_standard` by default and use `reviewer_deep` for
broad, subtle, security-sensitive, concurrency-sensitive, or whole-branch
changes. On another platform, dispatch a `general-purpose` subagent with an
explicit model appropriate to the same risk. Fill the template at
[code-reviewer.md](code-reviewer.md).
```

In `skills/requesting-code-review/code-reviewer.md`, replace only the dispatch
wrapper from `Subagent (general-purpose):` through `prompt: |` with:

```text
Subagent ([AGENT]):
  description: "Review code changes"
  model: [MODEL — REQUIRED on platforms without Codex custom-agent routing]
  prompt: |
```

Add these entries at the start of its existing `Placeholders` list:

```markdown
- `[AGENT]` — REQUIRED on Codex: `reviewer_standard` by default or
  `reviewer_deep` for broad, subtle, high-risk, or whole-branch review. The
  final review in subagent-driven development always uses `reviewer_deep`.
- `[MODEL]` — REQUIRED on platforms that use `general-purpose` instead of a
  named Codex custom agent.
```

Do not alter any line from `You are a Senior Code Reviewer` through the end of the existing prompt body.

- [ ] **Step 7: Run focused routing and configuration tests**

Run:

```bash
python3 -m unittest tests.test_superpowers_agent_routing tests.test_capability_bundle -v
```

Expected: all routing and capability-bundle tests pass.

- [ ] **Step 8: Run full repository verification**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -p 'test_*.py'
scripts/doctor.sh
git diff --check
```

Then, from `../codex-harness`, run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/capabilities/test_preflight.py -q
```

Expected: repository validation reports 11 agents; all unit tests pass; doctor reports `doctor passed`; `git diff --check` emits no output.
The existing harness model-preflight tests pass, confirming unavailable pinned
models still fail instead of falling back.

- [ ] **Step 9: Commit the Superpowers routing changes**

```bash
git add tests/test_superpowers_agent_routing.py skills/subagent-driven-development/SKILL.md skills/subagent-driven-development/implementer-prompt.md skills/subagent-driven-development/task-reviewer-prompt.md skills/requesting-code-review/SKILL.md skills/requesting-code-review/code-reviewer.md
git commit -m "feat: route Superpowers work by model tier"
```

# Explicit `agent_type` Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every active Codex role dispatch select its custom role with `agent_type` and disable full-history inheritance with `fork_turns="none"`.

**Architecture:** Keep model and reasoning configuration in the existing standalone agent TOML files. Change only the active orchestration instructions and templates so the dispatch call selects those definitions explicitly; regression tests enforce the call shape without altering the self-contained child prompt bodies.

**Tech Stack:** Markdown workflow skills and prompt templates, Python `unittest`, shell bootstrap and doctor scripts.

## Global Constraints

- `agent_type` is the only custom-role selector.
- `task_name` is a descriptive task label and must not be used as a role selector.
- Every role-changing Codex spawn uses `fork_turns="none"` and a self-contained message.
- If the surfaced tool lacks `agent_type` or `fork_turns="none"`, stop before dispatch instead of silently inheriting the parent model.
- Preserve historical plans and design documents.
- Do not change the existing agent TOML model, reasoning, sandbox, or developer-instruction values.

---

### Task 1: Enforce Explicit Custom-Role Dispatch

**Files:**
- Modify: `tests/test_superpowers_agent_routing.py`
- Modify: `skills/subagent-driven-development/SKILL.md`
- Modify: `skills/subagent-driven-development/implementer-prompt.md`
- Modify: `skills/subagent-driven-development/task-reviewer-prompt.md`
- Modify: `skills/requesting-code-review/SKILL.md`
- Modify: `skills/requesting-code-review/code-reviewer.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: custom-agent names and model routing from `.codex/agents/*.toml`.
- Produces: active dispatch instructions equivalent to `spawn_agent(agent_type=<role>, fork_turns="none", task_name=<label>, message=<self-contained prompt>)`.

- [ ] **Step 1: Add a failing regression test for the dispatch contract**

In `tests/test_superpowers_agent_routing.py`, change `prompt_hash` to extract the
body after `message: |`, update the three template-prefix expectations, and add
this test:

```python
    def test_active_codex_dispatches_use_agent_type_without_history_fork(self):
        active_dispatch_files = (
            "skills/subagent-driven-development/SKILL.md",
            "skills/subagent-driven-development/implementer-prompt.md",
            "skills/subagent-driven-development/task-reviewer-prompt.md",
            "skills/requesting-code-review/SKILL.md",
            "skills/requesting-code-review/code-reviewer.md",
            "README.md",
        )
        for relative in active_dispatch_files:
            text = self.read(relative)
            self.assertIn("agent_type", text, relative)
            self.assertIn('fork_turns="none"', text, relative)

        workflow = self.read("skills/subagent-driven-development/SKILL.md")
        self.assertIn("`agent_type` is the custom-role selector", workflow)
        self.assertIn("`task_name` is only a descriptive task label", workflow)
        self.assertIn(
            "report that native custom-role selection is unavailable and stop before "
            "dispatch",
            workflow,
        )
```

Update each template-prefix assertion to require this shape while keeping its
existing message body:

```text
spawn_agent:
  agent_type: [AGENT]
  fork_turns="none"
  task_name: "<descriptive label>"
  model: [MODEL — REQUIRED on platforms without Codex custom-agent routing;
         choose per SKILL.md Model Selection]
  message: |
```

Use `implement-task-n`, `review-task-n`, and `review-code-changes` as the three
descriptive labels. Leave the existing SHA-256 expectations unchanged so the
test proves that only dispatch metadata changed, not the child prompt bodies.

- [ ] **Step 2: Run the focused test and verify the new contract fails**

Run:

```bash
python3 -m unittest tests.test_superpowers_agent_routing -v
```

Expected: FAIL because the active files do not yet contain the required
`agent_type`/`fork_turns="none"` contract and the templates still use the old
`Subagent ([AGENT])` prefix.

- [ ] **Step 3: Add the shared dispatch rule to the active workflow skill**

In `skills/subagent-driven-development/SKILL.md`, immediately before the Codex
agent tier table, add:

```markdown
For every named Codex dispatch, pass the selected role as `agent_type`, set
`fork_turns="none"`, use a unique descriptive `task_name`, and put all child
context in the self-contained `message`. `agent_type` is the custom-role
selector; `task_name` is only a descriptive task label. Do not pass `model` or
`reasoning_effort` alongside a named role because its TOML definition owns
those settings.

If the surfaced `spawn_agent` tool does not expose `agent_type` or
`fork_turns="none"`, report that native custom-role selection is unavailable
and stop before dispatch. Do not substitute `task_name` as the selector or
claim that the configured model routing was applied.
```

- [ ] **Step 4: Convert the implementer and reviewer prompt headers**

In each of the three prompt-template files, replace only the dispatch metadata
above the unchanged child message body with:

```text
spawn_agent:
  agent_type: [AGENT]
  fork_turns="none"
  task_name: "implement-task-n"
  model: [MODEL — REQUIRED on platforms without Codex custom-agent routing;
         choose per SKILL.md Model Selection]
  message: |
```

Use `review-task-n` in `task-reviewer-prompt.md` and `review-code-changes` in
`code-reviewer.md`. Extend each `[AGENT]` placeholder explanation to say that
Codex passes the selected role as `agent_type` with `fork_turns="none"`; retain
the existing non-Codex `general-purpose` behavior.

- [ ] **Step 5: Update standalone review and README guidance**

In `skills/requesting-code-review/SKILL.md`, make the Codex dispatch paragraph
require the selected reviewer in `agent_type` with `fork_turns="none"` and a
self-contained message. State that a missing field blocks native custom-role
dispatch.

In `README.md`, follow the five-tier overview with this concise contract:

```markdown
Active Codex workflows pass the selected role through `agent_type` with
`fork_turns="none"`; `task_name` remains a descriptive label. If those spawn
arguments are unavailable, the workflow stops rather than silently inheriting
the parent model.
```

- [ ] **Step 6: Run focused tests and verify green**

Run:

```bash
python3 -m unittest tests.test_superpowers_agent_routing -v
```

Expected: all tests in `SuperpowersAgentRoutingTests` pass, including unchanged
message-body hashes.

- [ ] **Step 7: Inspect the surgical diff**

Run:

```bash
git diff --check
git diff -- README.md skills/subagent-driven-development/SKILL.md skills/subagent-driven-development/implementer-prompt.md skills/subagent-driven-development/task-reviewer-prompt.md skills/requesting-code-review/SKILL.md skills/requesting-code-review/code-reviewer.md tests/test_superpowers_agent_routing.py
```

Expected: no whitespace errors; only active dispatch metadata, explanations,
README guidance, and their tests change. Agent TOMLs and historical documents
remain unchanged.

- [ ] **Step 8: Run full verification and apply the portable config**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
./scripts/bootstrap.sh --apply
./scripts/doctor.sh
```

Expected: the complete test suite passes, bootstrap regenerates the current
global configuration successfully, and doctor ends with `doctor passed`.

- [ ] **Step 9: Commit the implementation**

```bash
git add README.md skills/subagent-driven-development/SKILL.md skills/subagent-driven-development/implementer-prompt.md skills/subagent-driven-development/task-reviewer-prompt.md skills/requesting-code-review/SKILL.md skills/requesting-code-review/code-reviewer.md tests/test_superpowers_agent_routing.py docs/superpowers/plans/2026-07-19-explicit-agent-type-dispatch.md
git commit -m "config: require explicit agent type dispatch"
```

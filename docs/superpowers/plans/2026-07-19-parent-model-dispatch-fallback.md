# Parent-Model Dispatch Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Codex implementation and review workflows running by inheriting the parent model whenever native `agent_type` selection is unavailable.

**Architecture:** Preserve the existing named custom-agent path and standalone role TOMLs. Add an explicit capability-based generic path that omits `agent_type`, retains a fresh self-contained child message, and accurately records parent-model inheritance.

**Tech Stack:** Markdown workflow skills and prompt templates, Python `unittest`, shell bootstrap and doctor scripts, Codex CLI smoke testing.

## Global Constraints

- Prefer configured custom roles when native `agent_type` selection exists.
- Missing `agent_type` alone is not a dispatch failure.
- Generic fallback omits `agent_type` and inherits the parent model and reasoning effort.
- Both paths use `fork_turns="none"`, a unique descriptive `task_name`, and a self-contained `message`.
- Never substitute `task_name` as a role selector or claim a Terra/Sol pin was applied on the generic path.
- Stop only if the surfaced tool cannot perform the generic contract or the generic spawn returns an error.
- Preserve standalone custom-agent TOMLs and their model, reasoning, sandbox, and developer-instruction values.
- Preserve historical plans and design documents.

---

### Task 1: Add Graceful Parent-Model Dispatch

**Files:**
- Modify: `tests/test_superpowers_agent_routing.py`
- Modify: `skills/subagent-driven-development/SKILL.md`
- Modify: `skills/subagent-driven-development/implementer-prompt.md`
- Modify: `skills/subagent-driven-development/task-reviewer-prompt.md`
- Modify: `skills/requesting-code-review/SKILL.md`
- Modify: `skills/requesting-code-review/code-reviewer.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the runtime-visible `spawn_agent` argument set and existing custom-agent tier mapping.
- Produces: named-role dispatch when `agent_type` exists; otherwise generic `spawn_agent(fork_turns="none", task_name=<unique label>, message=<self-contained prompt>)` with parent-model inheritance.

- [ ] **Step 1: Write failing assertions for supported generic fallback**

In `tests/test_superpowers_agent_routing.py`, replace
`test_active_codex_dispatches_use_agent_type_without_history_fork` with:

```python
    def test_active_codex_dispatches_fallback_to_parent_model(self):
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
            self.assertIn("parent model", text, relative)

        workflow = self.read("skills/subagent-driven-development/SKILL.md")
        self.assertIn("omit `agent_type` and dispatch a generic child", workflow)
        self.assertIn("inherits the parent model and reasoning effort", workflow)
        self.assertIn("Missing `agent_type` alone is not a dispatch failure", workflow)
        self.assertNotIn(
            "native custom-role selection is unavailable and stop before dispatch",
            workflow,
        )
        self.assertNotIn(
            "report it and stop before dispatch rather than silently inheriting",
            workflow,
        )
```

Extend `test_dispatch_templates_select_agents_without_replacing_prompt_contracts`
so each template must also contain this generic form:

```text
**Codex generic parent-model fallback:**

spawn_agent:
  fork_turns="none"
  task_name: "[TASK_NAME]"
  message: <same self-contained message body as the named form>
```

Keep all three existing SHA-256 message-body expectations unchanged.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python3 -m unittest tests.test_superpowers_agent_routing -v
```

Expected: FAIL because active instructions still stop when `agent_type` is
missing and the templates do not show the generic parent-model form.

- [ ] **Step 3: Replace the shared stop rule with capability-based fallback**

In `skills/subagent-driven-development/SKILL.md`, preserve the named-role
contract and replace the stop-before-dispatch paragraphs with:

```markdown
If the surfaced `spawn_agent` tool does not expose `agent_type`, omit
`agent_type` and dispatch a generic child with `fork_turns="none"`, the same
unique descriptive `task_name`, and the same self-contained `message`. That
child inherits the parent model and reasoning effort. Missing `agent_type`
alone is not a dispatch failure. Record the fallback accurately and do not
claim that a configured Terra/Sol role pin was applied.

Stop only if `message`, `task_name`, or `fork_turns="none"` is unavailable, or
if the generic spawn itself returns an error. Never substitute `task_name` as
a role selector.
```

Change the later unavailable-agent language so it directs the workflow to the
generic parent-model fallback rather than stopping.

- [ ] **Step 4: Add the generic form to all three dispatch templates**

Immediately after each named custom-agent form, add:

````markdown
**Codex generic parent-model fallback:** If `agent_type` is unavailable, omit
it and use the same self-contained message body shown above:

```text
spawn_agent:
  fork_turns="none"
  task_name: "[TASK_NAME]"
  message: <same self-contained message body as the named form>
```

This child inherits the parent model and reasoning effort. Do not claim the
`[AGENT]` role or its configured model was applied.
````

In each placeholder section, make `[AGENT]` required only when `agent_type` is
available. Preserve `[TASK_NAME]` uniqueness guidance, non-Codex behavior, and
the complete child prompt bodies byte-for-byte.

- [ ] **Step 5: Update standalone-review and README behavior**

In `skills/requesting-code-review/SKILL.md`, replace the blocked custom-role
language with the same generic parent-model fallback and its truthful-reporting
rule.

In `README.md`, replace the fail-closed paragraph with:

```markdown
Active Codex workflows prefer the selected custom role through `agent_type`
with `fork_turns="none"`. When `agent_type` is unavailable, they omit it and
dispatch a generic child that inherits the parent model and reasoning effort;
`task_name` remains only a unique descriptive label.
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```bash
python3 -m unittest tests.test_superpowers_agent_routing -v
```

Expected: all routing tests pass, including unchanged child-message hashes.

- [ ] **Step 7: Inspect the surgical diff**

Run:

```bash
git diff --check
git diff -- README.md skills/subagent-driven-development/SKILL.md skills/subagent-driven-development/implementer-prompt.md skills/subagent-driven-development/task-reviewer-prompt.md skills/requesting-code-review/SKILL.md skills/requesting-code-review/code-reviewer.md tests/test_superpowers_agent_routing.py
git diff --name-only -- .codex/agents
```

Expected: no whitespace errors; only active workflow behavior, templates,
README guidance, and routing assertions change; no agent TOML changes.

- [ ] **Step 8: Run complete verification**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
./scripts/doctor.sh
```

Expected: the complete suite passes and doctor ends with `doctor passed`. In an
isolated worktree, verify bootstrap apply against a temporary home and defer
the live global apply until after integration from the primary checkout.

- [ ] **Step 9: Commit the implementation**

```bash
git add README.md skills/subagent-driven-development/SKILL.md skills/subagent-driven-development/implementer-prompt.md skills/subagent-driven-development/task-reviewer-prompt.md skills/requesting-code-review/SKILL.md skills/requesting-code-review/code-reviewer.md tests/test_superpowers_agent_routing.py docs/superpowers/plans/2026-07-19-parent-model-dispatch-fallback.md
git commit -m "config: fall back to parent model subagents"
```

- [ ] **Step 10: Apply globally and smoke-test the generic path after integration**

From the primary checkout after local merge, run:

```bash
./scripts/bootstrap.sh --apply
./scripts/doctor.sh
```

Then launch a fresh `codex exec --json --sandbox read-only` session that first
confirms `agent_type` is absent and invokes the visible generic `spawn_agent`
form with `fork_turns="none"`, a unique `task_name`, and a self-contained child
message requesting an exact sentinel response.

Expected: the child starts and returns the sentinel using the parent model; the
controller reports generic parent-model fallback rather than a custom-role pin.

# Deep Implementation Sol Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `implementer_deep` the explicit Sol/high implementation option while keeping the generic, fast, and standard implementation roles on Terra.

**Architecture:** Preserve the existing named-agent routing structure and change only the deep tier's pinned model. Keep the executable TOML, routing skill, README, design/plan documentation, and contract tests consistent so capability preflight continues to reject unavailable pins instead of silently inheriting another model.

**Tech Stack:** TOML agent configuration, Markdown routing documentation, Python `unittest` contract tests.

## Global Constraints

- Pin `implementer_deep` to `gpt-5.6-sol` with `model_reasoning_effort = "high"`.
- Keep `implementer`, `implementer_fast`, and `implementer_standard` on `gpt-5.6-terra`.
- Keep every planning and review role on `gpt-5.6-sol`.
- Preserve the existing agent names, sandboxes, prompt contracts, and routing criteria.
- Do not change scheduler behavior, task decomposition, review loops, or fallback behavior.

---

### Task 1: Pin Deep Implementation To Sol

**Files:**
- Modify: `tests/test_capability_bundle.py`
- Modify: `tests/test_superpowers_agent_routing.py`
- Modify: `.codex/agents/implementer_deep.toml`
- Modify: `README.md`
- Modify: `skills/subagent-driven-development/SKILL.md`
- Modify: `docs/superpowers/specs/2026-07-16-superpowers-tiered-agent-routing-design.md`
- Modify: `docs/superpowers/plans/2026-07-16-superpowers-tiered-agent-routing.md`

**Interfaces:**
- Consumes: Codex custom-agent TOML fields `model` and `model_reasoning_effort`, plus the existing Superpowers model-selection table.
- Produces: An `implementer_deep` role that deterministically selects `gpt-5.6-sol` at high reasoning while all less-demanding implementation tiers remain on Terra.

- [ ] **Step 1: Change the contract expectations to Sol/high**

In `tests/test_capability_bundle.py`, set the deep tier expectation to:

```python
"implementer_deep": ("gpt-5.6-sol", "high", "workspace-write"),
```

In `tests/test_superpowers_agent_routing.py`, set the expected routing row to:

```python
"| Broad architectural context or substantial design judgment | "
"`implementer_deep` | `gpt-5.6-sol`, high |",
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_capability_bundle.py' -v
python3 -m unittest discover -s tests -p 'test_superpowers_agent_routing.py' -v
```

Expected: the capability-bundle suite fails because `.codex/agents/implementer_deep.toml` still selects Terra, and the routing suite fails because the active skill table still documents Terra.

- [ ] **Step 3: Apply the minimal configuration and documentation change**

In `.codex/agents/implementer_deep.toml`, use:

```toml
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
```

In `skills/subagent-driven-development/SKILL.md` and both dated routing documents, make the deep row `gpt-5.6-sol`, high and the standard row `gpt-5.6-terra`, medium. In `README.md`, state that the planner, reviewers, and deep implementation role use Sol while the other implementation roles use Terra. Do not alter routing criteria or agent instructions.

- [ ] **Step 4: Run focused verification and verify GREEN**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_capability_bundle.py' -v
python3 -m unittest discover -s tests -p 'test_superpowers_agent_routing.py' -v
python3 scripts/validate.py
git diff --check
```

Expected: 7 capability-bundle tests pass, 5 routing tests pass, validation reports 25 skills and 11 agents, and `git diff --check` produces no output.

- [ ] **Step 5: Review the final diff**

Run:

```bash
git diff -- .codex/agents/implementer_deep.toml README.md skills/subagent-driven-development/SKILL.md tests/test_capability_bundle.py tests/test_superpowers_agent_routing.py docs/superpowers/specs/2026-07-16-superpowers-tiered-agent-routing-design.md docs/superpowers/plans/2026-07-16-superpowers-tiered-agent-routing.md
```

Expected: every changed line directly supports the deep Sol/high routing choice; no unrelated configuration, documentation, or formatting changes appear.

- [ ] **Step 6: Commit the bounded change if requested**

```bash
git add .codex/agents/implementer_deep.toml README.md skills/subagent-driven-development/SKILL.md tests/test_capability_bundle.py tests/test_superpowers_agent_routing.py docs/superpowers/specs/2026-07-16-superpowers-tiered-agent-routing-design.md docs/superpowers/plans/2026-07-16-superpowers-tiered-agent-routing.md docs/superpowers/plans/2026-07-19-deep-implementation-sol-routing.md
git commit -m "config: route deep implementation to sol"
```

Expected: create the commit only when the user explicitly requests it; otherwise leave the verified working-tree changes uncommitted.

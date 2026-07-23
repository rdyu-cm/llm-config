# Planning Routing Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unambiguous intent-based planning-skill routing and worktree-first change isolation to the portable global Codex instructions.

**Architecture:** Keep the behavior declarative in `AGENTS.global.md`, which bootstrap already links into each Codex installation. Add a focused repository test that locks the important routing and merge-safety clauses without modifying vendored or generated gstack content.

**Tech Stack:** Markdown policy, Python `unittest`, repository validation script.

## Global Constraints

- Keep vendored and generated gstack skill prompts unchanged.
- Do not make brainstorming mandatory for diagnostics, mechanical edits, narrow bug fixes, or approved-spec execution.
- Do not run every gstack plan reviewer for every plan.
- Keep tracked changes in worktrees and require explicit approval before local merge.

---

### Task 1: Planning and worktree routing policy

**Files:**
- Modify: `tests/test_gstack_catalog.py`
- Modify: `AGENTS.global.md`

**Interfaces:**
- Consumes: Codex skill descriptions and the existing global-instructions bootstrap link.
- Produces: Human-readable `## Planning skill routing` and `## Worktree-first changes` policy sections enforced by a focused unit test.

- [x] **Step 1: Write the failing policy test**

Add assertions to `test_global_policy_preserves_model_aware_roles`:

```python
        self.assertIn("## Planning skill routing", policy)
        self.assertIn("material product, architecture, interface, or behavior choices", policy)
        self.assertIn("not required for diagnostics, mechanical edits", policy)
        self.assertIn("not automatic merely because a plan exists", policy)
        self.assertIn("## Worktree-first changes", policy)
        self.assertIn("explicit approval before merging", policy)
```

- [x] **Step 2: Run the focused test and verify it fails**

Run: `python3 -m unittest tests.test_gstack_catalog.GstackCatalogTests.test_global_policy_preserves_model_aware_roles -v`

Expected: `FAIL` because `AGENTS.global.md` does not yet contain `## Planning skill routing`.

- [x] **Step 3: Add the minimal global policy**

Append these sections to `AGENTS.global.md`:

```markdown
## Planning skill routing

Route planning skills by intent instead of running overlapping workflows by default.

- Use `gstack-office-hours` for new product ideas, unclear user needs, demand validation, positioning, or deciding whether something is worth building. Carry its conclusions into later design work without repeating discovery.
- Use `brainstorming` when a change has material product, architecture, interface, or behavior choices. It is the design and approval gate for those changes, but is not required for diagnostics, mechanical edits, narrowly scoped bug fixes, or execution of an already approved specification.
- Use `gstack-spec` when the requested output is an issue, ticket, or backlog item.
- Use `writing-plans` for an approved design that requires multi-step implementation.
- Use `gstack-autoplan` only when the user requests the complete automatic review gauntlet. Use an individual `gstack-plan-*` reviewer when explicitly requested or when its documented trigger clearly matches the plan. For example, suggest or invoke `gstack-plan-ceo-review` when scope or ambition is genuinely in question. Plan review is not automatic merely because a plan exists.

Explicit user instructions can select a narrower or more rigorous route.

## Worktree-first changes

Start tasks that will modify tracked repository files in an isolated Git worktree unless already in one, the user explicitly requests in-place work, the repository is not Git-based, or worktree creation is unavailable. If isolation is unavailable, report that limitation before editing in place.

Do not edit `main` directly. Verify work in the isolated worktree and obtain explicit approval before merging locally. After approval, merge, rerun relevant verification on the merged result, and only then remove the worktree and feature branch.
```

- [x] **Step 4: Run focused and repository validation**

Run: `python3 -m unittest tests.test_gstack_catalog.GstackCatalogTests.test_global_policy_preserves_model_aware_roles -v`

Expected: `OK` with one passing test.

Run: `python3 scripts/validate.py`

Expected: exit status 0 and a `validated` summary.

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`

Expected: exit status 0 with all tests passing.

- [x] **Step 5: Inspect and commit**

Run: `git diff --check && git status --short && git diff -- AGENTS.global.md tests/test_gstack_catalog.py`

Expected: no whitespace errors; only the planned policy, focused test, design record, and implementation plan are changed relative to the feature branch base.

```bash
git add AGENTS.global.md tests/test_gstack_catalog.py docs/superpowers/plans/2026-07-23-planning-routing-policy.md
git commit -m "feat: define planning and worktree routing"
```

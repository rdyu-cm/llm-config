# Unified Codex and Claude Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One repository that installs a Codex configuration, a Claude Code configuration, or both from a single command, with one copy of the shared skill library and a migration path for the machine already running the split layout.

**Architecture:** Restore the Codex surfaces the port deleted, describe each provider as a target rather than branching ad hoc, dispatch configuration merging on file format, restore dual-provider prose to the shared skills, and adopt existing links that point into a predecessor repository behind an explicit flag.

**Tech Stack:** Python 3.11+ standard library, Bash, PowerShell, JSON, TOML, Markdown/YAML frontmatter, unittest.

## Global Constraints

- Never break the live Codex installation on this machine without an explicit, reported action.
- Apply stays opt-in, the dry run stays non-mutating, and adoption stays behind `--adopt`.
- One copy of each skill; provider differences live inside the file, not in a fork.
- Codex must gain the coexistence fixes Claude Code already has, since `agent-session` installs hooks into both.
- Keep `claude-opus-5` for ordinary named agents and `claude-fable-5` for the difficult roles on the Claude side; leave Codex model routing as it is.
- Do not rename or move the checkout while a live installation points into it.

---

### Task 1: Restore the Codex Surfaces

**Files:**
- Restore: `.codex/**` (config, hooks.json, agents, hooks)
- Restore: `AGENTS.global.md`
- Restore: `profiles/*.config.toml`
- Restore: `skills/*/agents/**`
- Restore: `scripts/cleanup_legacy_gstack.py` only if still referenced
- Modify: `capability-bundle.toml`

**Interfaces:**
- Consumes: the common ancestor, which is `codex-config`'s HEAD.
- Produces: both provider trees side by side with no collisions.

- [ ] **Step 1: Restore the deleted paths from the common ancestor**

Check the Codex-only paths out of the merge base rather than reverting the port commit,
which also did work that must be kept.

- [ ] **Step 2: Verify nothing collides**

Run: `python3 scripts/validate.py && python3 -m unittest discover -s tests`

Expected: PASS unchanged, because the restored tree is disjoint from the Claude tree.

- [ ] **Step 3: Extend the capability catalog to both providers**

List the Codex components beside the Claude components so the catalog describes the
repository rather than one half of it.

### Task 2: Format-Dispatching Configuration Merge

**Files:**
- Modify: `scripts/sync_config.py`
- Modify: `tests/test_portable.py`

**Interfaces:**
- Consumes: a `--base` of either `.toml` or `.json`.
- Produces: merged output in the same format, with shared merge semantics.

- [ ] **Step 1: Test both formats through one entry point**

Assert TOML and JSON round-trip, that list-union and `--carry` behave identically in both,
and that a Codex `hooks` array from a third party survives the merge.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_portable -v`

Expected: FAIL because the merger is JSON-only.

- [ ] **Step 3: Dispatch load and render on suffix**

Restore the TOML renderer from the ancestor and select it by extension. Keep one `merge`,
one `union`, and one `--carry` implementation shared by both formats. Drop the
`runtime_overlay` enumeration, which `--carry` subsumes.

- [ ] **Step 4: Verify**

Run: `python3 -m unittest tests.test_portable -v`

Expected: PASS for both formats.

### Task 3: Provider Targets in the Installer

**Files:**
- Modify: `scripts/bootstrap.sh`
- Modify: `scripts/install.sh`
- Modify: `scripts/doctor.sh`
- Modify: `scripts/bootstrap.ps1`
- Modify: `tests/test_portable.py`

**Interfaces:**
- Consumes: `--target codex|claude|both`, or inference from CLIs on `PATH`.
- Produces: the correct link set and config per provider, with the other provider's home untouched.

- [ ] **Step 1: Test each target independently**

Rehearse Codex-only, Claude-only, and both against temporary homes. Assert Codex links
`AGENTS.md`, `hooks.json`, `hooks`, `agents`, and the profile files into `~/.codex` and
skills into `~/.agents/skills`; assert Claude links its own set; assert each single-target
run leaves the other home absent.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_portable -v`

Expected: FAIL because the installer only knows `~/.claude`.

- [ ] **Step 3: Introduce the target abstraction**

Replace hardcoded Claude paths with accessors keyed on `TARGET`. Keep per-entry linking for
both providers. Register MCP servers per provider: through the CLI for Claude, and inside
`config.toml` for Codex.

- [ ] **Step 4: Infer the target and report the inference**

Default to the CLIs present on `PATH`, print what was inferred before acting, and fail in
preflight when neither CLI is installed.

- [ ] **Step 5: Verify all three targets**

Run:

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/*.sh
./scripts/install.sh --dry-run
```

Expected: tests pass, syntax clean, and the dry run against the real home reports both
providers without mutating anything.

### Task 4: Adoption of a Live Split Installation

**Files:**
- Modify: `scripts/bootstrap.sh`
- Modify: `scripts/install.sh`
- Modify: `tests/test_portable.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing symlinks pointing into a predecessor repository.
- Produces: repointed links under `--adopt`, or an actionable conflict without it.

- [ ] **Step 1: Test adoption and refusal**

Seed a home whose links point into a predecessor checkout. Assert the default run refuses,
names the conflicting paths, and mutates nothing. Assert `--adopt` repoints exactly those
links, leaves unrecognized links alone, and is idempotent.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_portable -v`

Expected: FAIL because any differing link target is an unconditional conflict.

- [ ] **Step 3: Implement adoption**

Treat a link as adoptable when its target resolves inside a known predecessor repository.
Report every repoint. Leave anything unrecognized a conflict, and keep the default
non-adopting.

- [ ] **Step 4: Verify against the real machine, without applying**

Run `./scripts/install.sh --dry-run` and confirm it names the five live Codex links as
adoptable and changes nothing.

### Task 5: Dual-Provider Skills

**Files:**
- Modify: the shared skill files that encode provider-specific dispatch
- Modify: `tests/test_portable.py`

**Interfaces:**
- Consumes: both provider forms from the ancestor and from the current tree.
- Produces: one file per skill describing both providers.

- [ ] **Step 1: Assert no skill names one provider exclusively**

Test that files documenting agent dispatch mention both providers, so a future one-sided
edit fails rather than silently forking behavior again.

- [ ] **Step 2: Restore both provider forms**

Merge the Codex and Claude sections back into the dispatch templates,
`subagent-driven-development`, `requesting-code-review`, `cli-creator`, `executing-plans`,
and the `impeccable` references. Keep the corrections already made rather than reverting to
the ancestor's text.

- [ ] **Step 3: Verify**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
rg -n 'subsubagent|wants Codex to create' skills
```

Expected: validator and tests pass; no matches.

### Task 6: Final Verification and Rename

**Files:**
- Modify: `README.md`
- Modify: only files needed to fix verification defects

**Interfaces:**
- Consumes: the verified unified repository.
- Produces: a documented one-command install for either or both providers.

- [ ] **Step 1: Run complete verification**

Run the validator, full tests, shell syntax checks, all three target dry runs, and
`doctor.sh`. Rehearse Codex-only, Claude-only, both, and adoption against temporary homes.

- [ ] **Step 2: Document both providers and the migration**

Describe target selection, inference, adoption, and the prerequisites per provider.

- [ ] **Step 3: Report and propose the rename**

Report verification evidence. Propose renaming the checkout as a separate step, performed
by reinstalling rather than by moving a directory underneath live symlinks, and leave it to
explicit approval.

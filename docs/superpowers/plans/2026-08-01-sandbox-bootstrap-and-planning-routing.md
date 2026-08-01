# Sandbox, Bootstrap Coexistence, and Planning Routing Implementation Plan

> **Note:** This plan records work that has been implemented and verified. Steps are
> checked because they are complete, not because they are pending.

**Goal:** Make apply succeed and stay non-destructive on a machine that already runs Claude Code, restore sandbox parity with the Codex configuration, and route planning to Fable while main sessions stay on Opus.

**Architecture:** Link name-keyed discovery entries individually, fold unmanaged settings into the machine-local overlay instead of refusing or discarding them, accumulate list-valued settings across layers, enable Claude Code's OS-level sandbox as a guardrail rather than a hard gate, and pin planning to Fable by overriding the built-in `Plan` agent alongside the existing `planner`.

**Tech Stack:** Python 3.11+ standard library, Bash, PowerShell, JSON, Markdown/YAML frontmatter, unittest.

## Global Constraints

- Apply stays opt-in and the dry run stays non-mutating.
- Never treat a directory entry this repository does not own as a conflict.
- Never discard machine-local settings that have no portable counterpart.
- Keep the sandbox degradable: an unsupported platform or missing dependency warns rather than blocks.
- Preserve `gh` credential access; two skills in this library depend on it.
- Keep `claude-opus-5` for ordinary named agents and `claude-fable-5` for the difficult roles.
- Do not commit credentials, authentication state, or generated settings.

---

### Task 1: Planning Routing to Fable

**Files:**
- Create: `.claude/agents/Plan.md`
- Modify: `CLAUDE.global.md`
- Modify: `scripts/validate.py`
- Modify: `tests/test_portable.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Claude Code user-scope agent resolution, which lets a user agent override a built-in of the same name.
- Produces: a Fable-pinned `Plan` agent and a routing rule that delegates planning instead of switching the session model.

- [x] **Step 1: Extend the routing assertions**

Add `Plan` to the expected Fable set in both the validator and the routing test, keeping
the assertion exact so an unintended model change still fails.

- [x] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_portable -v`

Expected: FAIL because `.claude/agents/Plan.md` does not exist.

- [x] **Step 3: Add the Plan agent and the routing rule**

Define a read-only `Plan` agent on `claude-fable-5` whose prompt keeps the built-in
read-only planning contract. Add a `CLAUDE.global.md` rule that delegates real planning to
`planner` or `Plan` and forbids main sessions from switching their own model. Record in the
README that no setting changes the plan-mode model and that `opusplan` cannot express
Opus-resting plus Fable-planning.

- [x] **Step 4: Verify**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest tests.test_portable -v
```

Expected: validator reports 12 agents and all tests pass.

### Task 2: Vendored Skill Port Defects

**Files:**
- Modify: `skills/requesting-code-review/code-reviewer.md`
- Modify: `skills/subagent-driven-development/implementer-prompt.md`
- Modify: `skills/subagent-driven-development/task-reviewer-prompt.md`
- Modify: `skills/executing-plans/SKILL.md`
- Modify: `skills/cli-creator/SKILL.md`

**Interfaces:**
- Consumes: Claude Code `Agent` dispatch vocabulary.
- Produces: dispatch templates that name a real parameter and descriptions that name the acting agent correctly.

- [x] **Step 1: Correct the double-substituted dispatch key**

Replace `subsubagent_type` with `subagent_type` in the three dispatch templates. The key
was produced by substituting `agent_type` inside text that had already been rewritten, so
agents dispatched from these templates could not select a role.

- [x] **Step 2: Correct the truncated platform list and the stale acting agent**

Restore a grammatical platform list in `executing-plans`, and change the `cli-creator`
description so it names Claude Code rather than Codex as the acting agent. The description
is matched against during skill selection, so the stale name degrades routing.

- [x] **Step 3: Verify no stale references remain**

Run:

```bash
rg -n 'subsubagent|wants Codex to create|all qualify' skills
```

Expected: no matches.

### Task 3: Bootstrap Coexistence

**Files:**
- Modify: `scripts/sync_config.py`
- Modify: `scripts/bootstrap.sh`
- Modify: `scripts/bootstrap.ps1`
- Modify: `tests/test_portable.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: an existing `~/.claude` containing foreign discovery entries, an unmanaged `settings.json`, and a populated `settings.local.json`.
- Produces: per-entry links, an overlay that absorbs unmanaged settings, and a merge that accumulates list-valued keys.

- [x] **Step 1: Write coexistence tests first**

Test that unrelated `hooks.SessionStart` handlers from both layers survive a merge and that
a second merge does not duplicate them. Test that `--carry` folds unmanaged keys into the
overlay while the overlay wins on shared keys. Test that a dry run beside a foreign skill
directory exits zero, links repository skills individually, and does not mention the
foreign entry.

- [x] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_portable -v`

Expected: FAIL on list replacement, on the missing `--carry` flag, and on the
whole-directory skill link conflicting with the foreign entry.

- [x] **Step 3: Implement union merging and carry**

Add a `union` helper that appends portable list entries the local list does not already
contain, and dispatch to it from `merge` when both sides are lists. Add `--carry` to fold
unmanaged settings underneath the overlay and rewrite the overlay when it changes. Factor
the atomic write into a shared helper.

- [x] **Step 4: Implement per-entry linking and generated-output detection**

Add `link_children` in Bash and `Install-Children` in PowerShell, and use them for agents
and skills while hooks stay a whole-directory link. Replace the both-files-exist conflict
with a comparison against `.claude/settings.generated.json` that decides whether the
installed file is unmanaged and must be carried.

- [x] **Step 5: Verify against a real and a seeded home**

Run:

```bash
bash -n scripts/bootstrap.sh scripts/doctor.sh scripts/update.sh
python3 -m unittest discover -s tests -v
./scripts/bootstrap.sh
```

Then rehearse apply against a temporary home seeded with a foreign skill, an unmanaged
`settings.json` carrying a status line and third-party session hooks, and a populated
overlay. Confirm both hook layers survive, unmanaged keys are preserved, the foreign skill
is untouched, and a second apply leaves `settings.json` byte-identical.

Expected: dry run against the real home exits zero; the rehearsal reports both
`SessionStart` handlers, `IDEMPOTENT`, and the foreign entry still a real directory.

### Task 4: Sandbox

**Files:**
- Modify: `.claude/settings.json`
- Modify: `scripts/doctor.sh`
- Modify: `tests/test_portable.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Claude Code's `sandbox` settings schema, `bubblewrap` and `socat` on Linux.
- Produces: sandboxed Bash with network allowlisting and credential denial, degrading to a warning where unsupported.

- [x] **Step 1: Confirm the schema before writing it**

Read the `sandbox` schema from the running Claude Code build rather than from memory.
Invalid keys are dropped silently with an ignored-field warning, so an unverified key would
appear to work while doing nothing.

- [x] **Step 2: Assert the guardrail posture in tests**

Test that the sandbox is enabled, that `failIfUnavailable` is false and
`allowUnsandboxedCommands` is true, that Claude Code's own credential file and `~/.ssh` are
protected, that every credential entry uses a valid mode, and that instance metadata is
denied.

- [x] **Step 3: Add the sandbox block and dependency reporting**

Enable the sandbox with an allowlist covering this toolchain, unconditional
instance-metadata denial, write protection for shell and configuration state, and credential
denial that deliberately spares `gh`. Report Linux sandbox dependencies from `doctor.sh` as
optional, matching `failIfUnavailable: false`.

- [x] **Step 4: Validate against the running build**

Run `claude doctor` with the generated settings in place and confirm no schema validation
warning names the sandbox block.

Expected: no ignored-field warning. Record any genuine finding the check surfaces.

- [x] **Step 5: Document the posture and its limits**

Document why the sandbox degrades rather than gates, why `gh` is spared, that user-scope
sandbox paths resolve relative to `~/.claude` rather than the project, and that Linux drops
glob patterns when permission rules are translated into sandbox filesystem rules.

### Task 5: Final Verification

**Files:**
- Modify: only files needed to fix verification defects

**Interfaces:**
- Consumes: the complete change set on an isolated branch.
- Produces: a verified branch left for explicit integration approval.

- [x] **Step 1: Run complete verification**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap.sh scripts/doctor.sh scripts/update.sh
./scripts/bootstrap.sh
./scripts/doctor.sh
git diff --check
```

Expected: validator, tests, syntax checks, dry run, and doctor all pass.

- [x] **Step 2: Commit to an isolated branch and stop**

Commit the change set on a branch rather than `main`, and leave integration to explicit
approval as the global instructions require.

- [x] **Step 3: Report**

Report the verification evidence, the behavior changes the sandbox introduces, the
unverified PowerShell path, and the missing `socat` dependency on this host.

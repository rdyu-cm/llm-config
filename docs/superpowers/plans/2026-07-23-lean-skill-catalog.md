# Lean Skill Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the complete gstack integration, safely clean installations made by it, and add two concise original skills while preserving all independent portable-config improvements.

**Architecture:** Treat `eadfa3c` as the pre-gstack architectural reference but edit mixed files surgically. Keep the existing personal catalog intact, add two repository-owned skills, use a small Python migration helper from both bootstrap entrypoints, and delete all vendored/generated gstack runtime and maintenance code.

**Tech Stack:** Markdown skill files, Python 3.11 standard library, Bash, PowerShell, TOML, `unittest`.

## Global Constraints

- Do not copy gstack wording, prompt structure, scripts, or runtime behavior.
- Do not compress or otherwise edit existing non-gstack skill descriptions.
- Preserve the regular-file `config.toml` fix, Codebase Memory prewarming, agents, profiles, hooks, and general worktree policy.
- Cleanup may unlink only targets recorded in a valid version-1 legacy state file when the target is still the exact recorded symlink.
- Do not merge into `main` without explicit user approval.

---

### Task 1: Add the two lean skills

**Files:**
- Create: `skills/explain-as-you-go/SKILL.md`
- Create: `skills/project-health/SKILL.md`
- Modify: `capability-bundle.toml`
- Modify: `tests/test_capability_bundle.py`

**Interfaces:**
- Consumes: existing skill discovery under `skills/*/SKILL.md`.
- Produces: two cataloged, discoverable original skills.

- [ ] **Step 1: Write failing catalog and behavior tests**

Add tests that assert the catalog contains `explain-as-you-go` and `project-health`; the former contains all three mode names plus scientific interpretation, units, numerical assumptions, and falsification; the latter requires repository-native checks, read-only diagnosis, and separate authorization for fixes.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python3 -m unittest tests.test_capability_bundle -v`

Expected: FAIL because the two skills do not exist.

- [ ] **Step 3: Write the minimal original skill files**

Give each file valid `name` and concise `description` frontmatter. `explain-as-you-go` must default to guided depth, explain only meaningful reasoning, cover the scientific requirements, and remain opt-in. `project-health` must discover native project commands, run non-mutating checks from narrow to broad, distinguish tool failure from product failure, and stop after reporting unless fixes were requested.

- [ ] **Step 4: Add catalog entries**

Register both paths as supported skills in `capability-bundle.toml`. Do not modify any existing skill description.

- [ ] **Step 5: Run focused validation**

Run: `python3 -m unittest tests.test_capability_bundle -v && python3 scripts/validate.py`

Expected: PASS, reporting 27 personal skills.

- [ ] **Step 6: Commit**

```bash
git add skills/explain-as-you-go skills/project-health capability-bundle.toml tests/test_capability_bundle.py
git commit -m "feat: add lean learning and health skills"
```

### Task 2: Add a safe one-time installed-state cleanup

**Files:**
- Create: `scripts/cleanup_legacy_gstack.py`
- Create: `tests/test_cleanup_legacy_gstack.py`
- Modify: `scripts/bootstrap.sh`
- Modify: `scripts/bootstrap.ps1`
- Modify: `tests/test_bootstrap.py`

**Interfaces:**
- Produces: `cleanup(home: Path, apply: bool) -> list[str]`, which reports actions or raises `ValueError` without removing user-owned paths.
- Bootstrap invokes `python cleanup_legacy_gstack.py --home HOME [--apply]` exactly once before discovery links are installed.

- [ ] **Step 1: Write failing cleanup unit tests**

Cover absent state, dry-run immutability, successful removal of exact recorded symlinks, regular-file conflict, changed-symlink conflict, malformed JSON, symlinked state-file rejection, version rejection, non-object `links`, and all-or-nothing preflight when one of multiple targets conflicts.

Use state shaped as:

```python
{
    "version": 1,
    "mode": "full",
    "links": {str(target): str(source)},
}
```

- [ ] **Step 2: Run cleanup tests and verify failure**

Run: `python3 -m unittest tests.test_cleanup_legacy_gstack -v`

Expected: FAIL because `scripts.cleanup_legacy_gstack` does not exist.

- [ ] **Step 3: Implement bounded cleanup**

Parse the state with `json.loads`. Reject a symlinked/non-regular state path, wrong version, non-dictionary root, non-dictionary links, non-string paths, targets outside `home`, and any recorded target that is neither absent nor the exact recorded symlink. Preflight every target before mutation. On apply, unlink matching symlinks and then unlink the state; on dry-run, return `would   remove ...` messages only. Missing targets are safe and allow stale state removal.

- [ ] **Step 4: Add bootstrap integration tests**

In the Bash fixture tests, assert one `--apply` removes an exact legacy managed link and state, while a changed target makes bootstrap exit nonzero before discovery-link mutation. Assert the obsolete `--gstack=...` flag exits 2. Add a PowerShell source assertion that it invokes the same cleanup helper with `--apply` only in apply mode.

- [ ] **Step 5: Wire both bootstrap entrypoints**

Remove the gstack mode parser and prepare/install/update calls from Bash. After config installation and Codebase Memory prewarming, call the cleanup helper and stop before discovery-link installation on conflict. In PowerShell, invoke the same helper using its existing Python interpreter and propagate nonzero status.

- [ ] **Step 6: Run focused tests**

Run: `python3 -m unittest tests.test_cleanup_legacy_gstack tests.test_bootstrap -v`

Expected: PASS; a single apply cleans exact legacy links, and conflicts remain untouched.

- [ ] **Step 7: Commit**

```bash
git add scripts/cleanup_legacy_gstack.py scripts/bootstrap.sh scripts/bootstrap.ps1 tests/test_cleanup_legacy_gstack.py tests/test_bootstrap.py
git commit -m "fix: clean legacy gstack links safely"
```

### Task 3: Remove gstack repository integration and retain independent policy

**Files:**
- Delete: `vendor/gstack/`
- Delete: `vendor/gstack-source.toml`
- Delete: `generated/gstack-codex/`
- Delete: `generated/gstack-codex-workflow/`
- Delete: `gstack-capabilities.toml`
- Delete: `scripts/gstack_updates.py`
- Delete: `scripts/install_gstack.py`
- Delete: `scripts/prepare_gstack.py`
- Delete: `scripts/update-gstack.sh`
- Delete: `scripts/update_gstack.py`
- Delete: `tests/test_gstack_catalog.py`
- Delete: `tests/test_gstack_updates.py`
- Delete: `tests/test_gstack_vendor.py`
- Delete: `tests/test_install_gstack.py`
- Delete: `tests/test_prepare_gstack.py`
- Delete: `tests/test_update_gstack.py`
- Delete: `docs/superpowers/specs/2026-07-22-gstack-integration-design.md`
- Delete: `docs/superpowers/plans/2026-07-22-gstack-integration.md`
- Modify: `.codex/hooks/session_context.py`
- Modify: `AGENTS.global.md`
- Modify: `README.md`
- Modify: `scripts/doctor.sh`
- Modify: `scripts/update.sh`
- Modify: `scripts/validate.py`
- Modify: `sources.lock.toml`
- Modify: `tests/test_doctor.py`
- Modify: `tests/test_hooks.py`
- Modify: `tests/test_external_cwd.py`

**Interfaces:**
- Consumes: the Task 2 cleanup helper as the only remaining legacy reference.
- Produces: a source catalog and runtime with no gstack integration, while retaining config-current checks, hook tests, Codebase Memory checks, and planning/worktree policy.

- [ ] **Step 1: Replace integration assertions with absence assertions**

Delete gstack-specific doctor and hook tests. Add a repository hygiene test that enumerates tracked files outside the current design, plan, cleanup helper, and cleanup tests, and rejects active `gstack` references. Keep the existing external-working-directory doctor contract test.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python3 -m unittest tests.test_capability_bundle tests.test_doctor tests.test_hooks tests.test_external_cwd -v`

Expected: FAIL while integration files and mixed-file references remain.

- [ ] **Step 3: Delete dedicated integration artifacts**

Remove the exact dedicated paths listed above. Do not remove any non-gstack skill, agent, hook, profile, license, or source entry.

- [ ] **Step 4: Surgically clean mixed files**

Remove update-notice imports and logic from `session_context.py`; gstack source/catalog validation from `validate.py`; runtime-state validation from `doctor.sh`; gstack documentation from README; the gstack source table from `sources.lock.toml`; and updater special-casing from `scripts/update.sh`.

In `AGENTS.global.md`, remove the gstack subagent section. Retain a planning section containing only the `brainstorming` and `writing-plans` routing principles plus the explicit-user override, and retain the complete worktree-first section.

- [ ] **Step 5: Run focused tests and static reference scan**

Run: `python3 -m unittest tests.test_capability_bundle tests.test_doctor tests.test_hooks tests.test_external_cwd -v`

Run: `rg -n -i "gstack|gbrain|garry|yc office" --glob '!docs/superpowers/specs/2026-07-23-lean-skill-catalog-design.md' --glob '!docs/superpowers/plans/2026-07-23-lean-skill-catalog.md' --glob '!scripts/cleanup_legacy_gstack.py' --glob '!tests/test_cleanup_legacy_gstack.py'`

Expected: tests PASS; scan returns no matches.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove gstack integration"
```

### Task 4: Verify the lean installation end to end

**Files:**
- Modify only files required by a failing verification attributable to Tasks 1–3.

**Interfaces:**
- Produces: evidence that the repository and a clean temporary installation contain 27 personal skills, no active gstack integration, current generated config, and a sub-2% metadata estimate.

- [ ] **Step 1: Run the complete unit suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS with zero failures.

- [ ] **Step 2: Run repository validation and whitespace checks**

Run: `python3 scripts/validate.py && git diff --check`

Expected: PASS; validation reports 27 personal skills and the whitespace check is empty. Separately render the 27 personal descriptions in Codex's exposed-list shape, add the previously measured system-skill metadata, estimate at four UTF-8 bytes per token, and report the result against the 5,168-token allowance without committing an estimator.

- [ ] **Step 3: Run bootstrap and doctor smoke checks in a temporary home**

Run bootstrap dry-run with a temporary `HOME`, then apply using a fake successful `npx` on `PATH`, then run doctor against that home. Assert `~/.agents/skills` resolves to this worktree's `skills`, `~/.codex/config.toml` is a regular file, no `gstack-*` entry exists below `~/.codex/skills`, and no legacy state remains.

Expected: bootstrap apply and doctor exit 0.

- [ ] **Step 4: Review the final diff against the preservation boundary**

Run: `git diff 95953ab...HEAD --stat && git diff 95953ab...HEAD -- AGENTS.global.md scripts/bootstrap.sh scripts/bootstrap.ps1 scripts/doctor.sh scripts/validate.py`

Expected: all changed lines trace to the approved design; regular-file config handling, Codebase Memory prewarming, agents, profiles, hooks, and worktree-first policy remain.

- [ ] **Step 5: Commit any verification-only correction**

If Step 1–4 required a correction, stage only that correction and commit it as `fix: complete lean catalog migration`. If no correction was required, do not create an empty commit.

- [ ] **Step 6: Request merge approval**

Report the branch, commits, test counts, measured skill metadata, cleanup behavior, and any skipped checks. Do not merge until the user explicitly approves.

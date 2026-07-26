# Claude-Native Config Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a full-history, Claude Code-native portable configuration repository that installs to `~/.claude` only when explicitly applied.

**Architecture:** Replace Codex discovery/configuration surfaces with Claude Code's documented user-level surfaces while retaining the audited skills, safety hooks, agents, source locks, and dry-run-first workflow. Keep machine-local state outside the repository, express model routing in agent frontmatter, and validate all static contracts without requiring an installed Claude CLI.

**Tech Stack:** Python 3.11+ standard library, Bash, PowerShell, JSON, TOML, Markdown/YAML frontmatter, unittest.

## Global Constraints

- Preserve the source repository's full Git history.
- Do not install Claude Code, modify `~/.claude`, or run bootstrap apply.
- Use `claude-opus-5` for ordinary named agents.
- Use `claude-fable-5` only for planner, deep implementer, deep reviewer, and security reviewer.
- Keep cross-session scheduling out of both config repositories; document it as a future harness responsibility.
- Preserve credentials, authentication state, transcripts, caches, and machine-local settings outside Git.
- Keep Linux shell and Windows PowerShell dry-run/apply entry points.

---

### Task 1: Claude-Native Configuration Contracts

**Files:**
- Create: `CLAUDE.global.md`
- Rename: `AGENTS.md` to `CLAUDE.md`
- Create: `.claude/settings.json`
- Create: `.claude/mcp.json`
- Create: `.claude/agents/*.md`
- Create: `profiles/{minimal,frontend,security,full}.settings.json`
- Modify: `.gitignore`
- Delete: `AGENTS.global.md`
- Delete: `.codex/config.toml`
- Delete: `.codex/agents/*.toml`
- Delete: `profiles/*.config.toml`
- Test: `tests/test_capability_bundle.py`

**Interfaces:**
- Consumes: Claude Code user settings, agent-frontmatter, skills, and MCP formats documented in the design.
- Produces: `settings.json` dictionaries mergeable by `scripts/sync_config.py`; agent Markdown with `name`, `description`, `model`, `tools`, and `permissionMode`.

- [ ] **Step 1: Rewrite configuration tests to assert Claude paths and routing**

Assert that every `.claude/agents/*.md` agent has valid frontmatter, ordinary roles use
`claude-opus-5`, and exactly `planner`, `implementer-deep`, `reviewer-deep`, and
`security-reviewer` use `claude-fable-5`. Assert settings contain `PreToolUse` and
`SessionStart`, and profiles contain explicit MCP enable/disable lists.

- [ ] **Step 2: Run the focused tests and confirm the old layout fails**

Run: `python3 -m unittest tests.test_capability_bundle -v`

Expected: FAIL because `.claude/settings.json` and Markdown agents do not exist.

- [ ] **Step 3: Create the Claude-native files and remove superseded Codex files**

Use Claude Code settings JSON with schema URL, workspace-safe permissions, and command
hooks. Define user agents in Markdown frontmatter; use read-only tool lists for research
and review roles and workspace tools for implementers. Keep MCP server definitions in
portable JSON without secrets and disable GitHub by default.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_capability_bundle -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add CLAUDE.md CLAUDE.global.md .claude profiles .gitignore tests/test_capability_bundle.py
git add -u AGENTS.global.md .codex profiles
git commit -m "feat: add Claude-native configuration"
```

### Task 2: Hook Translation and Validation

**Files:**
- Move: `.codex/hooks/*.py` to `.claude/hooks/*.py`
- Modify: `.claude/hooks/session_context.py`
- Modify: `.claude/hooks/command_policy.py`
- Modify: `.claude/hooks/secret_guard.py`
- Delete: `.codex/hooks.json`
- Modify: `tests/test_hooks.py`
- Modify: `scripts/validate.py`

**Interfaces:**
- Consumes: Claude Code hook JSON on stdin with `tool_name` and `tool_input`.
- Produces: Claude hook decision JSON using `hookSpecificOutput.permissionDecision`; validator exit code 0 only for a complete native layout.

- [ ] **Step 1: Update hook and validator tests**

Point hook tests at `.claude/hooks`, assert Claude wording, and add tests that Edit/Write
`file_path` and `content` payloads are inspected in addition to Bash command payloads.
Update validation expectations to JSON settings, Markdown agents, model routing, and four
JSON profiles.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_hooks -v`

Expected: FAIL on missing `.claude/hooks`.

- [ ] **Step 3: Translate hook implementations and validator**

Keep catastrophic command rules. Make the secret guard extract file paths and content
from Claude's `Edit` and `Write` payloads as well as command/patch text. Change all policy
messages to “Portable Claude Code”. Parse simple YAML frontmatter without adding a PyYAML
dependency.

- [ ] **Step 4: Verify hooks and repository validator**

Run:

```bash
python3 -m unittest tests.test_hooks -v
python3 scripts/validate.py
```

Expected: all hook tests pass and validator reports skill, agent, hook, and profile counts.

- [ ] **Step 5: Commit**

Run:

```bash
git add .claude/hooks scripts/validate.py tests/test_hooks.py
git add -u .codex
git commit -m "feat: port safety hooks to Claude Code"
```

### Task 3: Dry-Run-First Bootstrap and Local Settings Merge

**Files:**
- Modify: `scripts/sync_config.py`
- Modify: `scripts/bootstrap.sh`
- Modify: `scripts/bootstrap.ps1`
- Modify: `scripts/doctor.sh`
- Delete: the retired Codex integration cleanup helper
- Modify: `tests/test_sync_config.py`
- Modify: `tests/test_bootstrap.py`
- Modify: `tests/test_doctor.py`
- Delete: the retired Codex integration cleanup tests
- Delete: the retired integration reference-policy test

**Interfaces:**
- Consumes: repository `.claude/settings.json`, optional `~/.claude/settings.local.json`, and an explicit `--apply`/`-Apply`.
- Produces: generated `.claude/settings.generated.json`, installed regular `~/.claude/settings.json`, and links for `CLAUDE.md`, agents, hooks, and skills.

- [ ] **Step 1: Rewrite bootstrap and merge tests**

Test recursive JSON-object merge with portable values winning, array replacement rather
than concatenation, preservation of an existing user settings file as
`settings.local.json`, refusal to overwrite unmanaged conflicts, default dry run, and no
real-home mutation. Test that apply fails clearly when `claude` is absent if CLI-managed
MCP installation is required.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_sync_config tests.test_bootstrap tests.test_doctor -v`

Expected: FAIL because the scripts still target TOML and `~/.codex`.

- [ ] **Step 3: Implement JSON merging and Claude bootstrap**

Replace TOML parsing with `json`. Target `~/.claude`, preserve local settings, atomically
install a regular settings file, link repository-owned directories, and keep default
execution non-mutating. Remove retired Codex legacy-cleanup behavior rather than carrying
it into a fresh Claude installation.

- [ ] **Step 4: Run focused tests and shell checks**

Run:

```bash
python3 -m unittest tests.test_sync_config tests.test_bootstrap tests.test_doctor -v
bash -n scripts/bootstrap.sh scripts/doctor.sh scripts/update.sh
```

Expected: all tests pass and Bash reports no syntax errors.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts tests
git add -u
git commit -m "feat: add Claude Code bootstrap and doctor"
```

### Task 4: Skills, Catalog, Profiles, and Documentation

**Files:**
- Modify: `skills/*/SKILL.md` where active instructions reference Codex-only tools, agent APIs, or config paths
- Modify: `skills/*/agents/openai.yaml`
- Modify: `capability-bundle.toml`
- Modify: `sources.lock.toml`
- Modify: `plugins.lock.toml`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `tests/test_superpowers_agent_routing.py`
- Modify: `tests/test_external_cwd.py`
- Modify: remaining repository tests with Codex-path assumptions

**Interfaces:**
- Consumes: retained vendored skills and source/license pins.
- Produces: a catalog whose paths all exist and instructions that invoke Claude Code's `Agent`/skills vocabulary without Codex-only routing parameters.

- [ ] **Step 1: Add stale-reference and catalog assertions**

Assert that first-party active files contain no `.codex`, `AGENTS.global.md`, `gpt-5`,
`spawn_agent`, `fork_turns`, or OpenAI-docs routing except in historical design/plan
documents, upstream provenance, licenses, and explicitly comparative security references.

- [ ] **Step 2: Run repository tests and observe failures**

Run: `python3 -m unittest discover -s tests -v`

Expected: FAIL on stale paths and routing contracts.

- [ ] **Step 3: Translate active skill integrations and documentation**

Change agent dispatch examples to Claude's `Agent` tool vocabulary, replace Codex global
paths with Claude paths, retain generic Agent Skills content, preserve upstream licenses,
and explain intentional historical references. Update the capability catalog to point at
`.claude` components and describe harness scheduling as external.

- [ ] **Step 4: Run full tests and reference audit**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
rg -n '\.codex|AGENTS\.global|gpt-5|spawn_agent|fork_turns' \
  README.md CLAUDE.md AGENTS.md .claude profiles scripts tests capability-bundle.toml skills
```

Expected: tests and validator pass; any search hits are reviewed and limited to
intentional compatibility/history text.

- [ ] **Step 5: Commit**

Run:

```bash
git add README.md CLAUDE.md AGENTS.md .env.example .claude profiles scripts tests skills \
  capability-bundle.toml sources.lock.toml plugins.lock.toml
git commit -m "docs: complete Claude-native portable config"
```

### Task 5: Final Verification and Destination Materialization

**Files:**
- Modify: only files needed to fix verification defects
- Create destination: `/home/rdyu/claude/claude-config`

**Interfaces:**
- Consumes: clean `claude-native-port` branch with passing checks.
- Produces: standalone local clone at the requested destination, with full history and no changes to `~/.claude`.

- [ ] **Step 1: Run complete verification**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap.sh scripts/doctor.sh scripts/update.sh
./scripts/bootstrap.sh
./scripts/doctor.sh
git diff --check
git status --short --branch
```

Expected: validator/tests/syntax/dry-run/doctor pass; Git reports no uncommitted changes.

- [ ] **Step 2: Verify model and mutation boundaries**

Run a static query over agent frontmatter and confirm exactly four Fable roles. Run
bootstrap with an isolated temporary `HOME` in dry-run mode and confirm no files are
created below it. Confirm `/home/rdyu/.claude` remains absent or byte-for-byte unchanged.

- [ ] **Step 3: Materialize the standalone destination**

Create `/home/rdyu/claude` if needed and clone the isolated branch locally to
`/home/rdyu/claude/claude-config`. Do not use `--apply`.

- [ ] **Step 4: Verify the destination**

Run the validator, full tests, dry-run bootstrap, Git log ancestry check, and clean-status
check from `/home/rdyu/claude/claude-config`.

- [ ] **Step 5: Report**

Report the destination, migration commits, exact verification results, documented
runtime limitation (Claude Code absent), and confirmation that `~/.claude` was untouched.

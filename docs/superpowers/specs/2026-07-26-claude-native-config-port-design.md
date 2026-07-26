# Claude-Native Portable Config Port

## Goal

Create `~/claude/claude-config` as a Claude Code-native fork of the portable Codex
configuration repository. Preserve the source repository's Git history, audited
dependencies, licensing, safety posture, and dry-run-first installation model while
translating supported capabilities to Claude Code's current configuration surfaces.

The migration must not install Claude Code, modify `~/.claude`, or apply the generated
configuration. Cross-session scheduling and mutual exclusion belong to a future shared
harness and are outside this repository.

## Architecture

The fork remains the source of truth and targets Claude Code's user-level configuration:

- `CLAUDE.md` contains compact global behavioral instructions.
- `.claude/settings.json` contains portable settings, permissions, and hooks.
- `.claude/agents/*.md` defines custom subagents using YAML frontmatter.
- `.claude/skills/` exposes the audited skill library through Claude Code's native skill
  discovery.
- Claude-supported MCP configuration replaces Codex TOML MCP definitions.
- Bootstrap scripts provide a non-mutating dry run by default and an explicit apply mode.
  Apply mode preserves existing machine-local settings and requires an installed Claude
  Code CLI where CLI-managed state is necessary.

Codex-only formats and metadata are removed or translated rather than retained under
misleading names.

## Model Routing

`claude-opus-5` is the default model for named agents. The following explicitly difficult
roles use `claude-fable-5`:

- planner
- deep implementer
- deep reviewer
- security reviewer

No global instruction asks the main session to switch models automatically. This keeps
Fable usage predictable and limited to named roles.

## Component Migration

Portable skills are retained and adapted where they reference Codex-only tools, model
names, agent metadata, or routing syntax. Unsupported OpenAI-specific integrations are
replaced with Claude/Anthropic equivalents only when an official supported mechanism
exists; otherwise they are removed and the omission is documented.

Hooks retain the original goals—session guidance, catastrophic-command blocking, and
secret protection—but use Claude Code's settings-based hook schema and hook input/output
contracts. There is no standalone `.claude/hooks.json`.

Profiles remain audited configuration variants where Claude Code can express the
distinction safely. The port does not emulate Codex profile behavior through hidden auth
directories or other fragile mechanisms.

Linux shell and Windows PowerShell bootstrap paths remain supported. Source locks,
capability manifests, update checks, licensing, documentation, and relevant regression
tests are updated for the Claude-native layout.

## Safety and Local State

The repository never stores credentials, authentication state, transcripts, caches,
trust decisions, or generated machine-local settings. Bootstrap is dry-run-only unless
the user supplies the apply flag. Existing unmanaged files are conflicts, not overwrite
targets. Apply behavior uses staged/atomic replacement where practical.

The migration does not run apply because Claude Code is not installed. It also does not
add a skill for cross-session waiting: reliable discovery, leases, heartbeats, fairness,
stale-lock recovery, and wakeups require a separate coordinator harness.

## Verification

Verification covers:

- repository validator and full native tests;
- JSON, TOML, YAML frontmatter, Python, shell, and PowerShell-relevant static checks;
- bootstrap dry runs against isolated temporary home directories;
- executable modes and symlink targets;
- agent model assignments and role-specific Fable routing;
- stale Codex/OpenAI reference review with documented intentional exceptions;
- Git history, clean worktree state, and final migration commits.

Because Claude Code is not installed, runtime CLI validation and apply-mode integration
are explicitly deferred. The dry run must explain that requirement without mutating the
real home directory.

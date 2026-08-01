# Sandbox, Bootstrap Coexistence, and Planning Routing

## Goal

Make `scripts/bootstrap.sh --apply` succeed on a machine that already runs Claude Code,
restore the sandbox parity that the Codex-to-Claude port dropped, and route planning work
to Fable while main sessions stay on Opus.

The port produced a configuration that validates cleanly but cannot install itself onto a
used machine, and that silently discards a working integration if it ever did. Both are
install-time defects rather than content defects, so the fixes belong in the bootstrap
contract rather than in the settings payload.

## Problem

Applying the current bootstrap against a real `~/.claude` fails or destroys state in three
independent ways.

`~/.claude/skills` and `~/.claude/agents` are name-keyed discovery directories that other
tools install into. `agent-session` places `wait-for-agent-session` in the first of them.
Linking the directory itself makes any pre-existing entry an unresolvable conflict, so
apply exits before doing anything.

`install_settings` treats `~/.claude/settings.json` and `~/.claude/settings.local.json`
both existing as a conflict requiring manual merge. Claude Code writes both files on its
own — the overlay appears the first time a permission is granted from a session whose
working directory is the home directory — so the "preserve existing settings" path only
works on a machine that has never been used.

`sync_config.merge` replaces lists instead of combining them. The portable
`hooks.SessionStart` array therefore overwrites the `agent-session` handler while
`SessionEnd`, `Stop`, `StopFailure`, and `UserPromptSubmit` survive, leaving a half-wired
integration that reports no error. The same replacement discards an accumulated
`permissions.allow` list.

Separately, the port mapped Codex's `approval_policy` onto `permissions.defaultMode` and
dropped `sandbox_mode = "workspace-write"` entirely, leaving pattern-matching hooks as the
only containment. Claude Code has a real OS-level sandbox that the port never adopted.

Finally, `planner` was already pinned to Fable but nothing routed to it: neither
`CLAUDE.global.md` nor any agent definition referenced it, and Claude Code's built-in
`Plan` subagent inherits the parent model.

## Architecture

### Installation

Agents and skills are linked entry by entry into directories the repository creates but
does not own. A neighbour this repository did not install is left untouched rather than
treated as a conflict. Hooks remain a whole-directory link because nothing else writes
there and settings reference those scripts by absolute path.

Settings installation stops treating the presence of either file as a conflict. The
repository owns `~/.claude/settings.json`; anything in it that the repository did not
generate is unmanaged and is folded underneath the machine-local overlay before merging,
rather than discarded. Apply recognizes its own previous output by comparing the installed
file against `.claude/settings.generated.json`. That comparison is what keeps portable
values from being baked into the overlay on every rerun, and it makes a direct user edit
between applies survive as machine-local rather than being lost.

### Merge contract

Objects continue to merge recursively with portable values winning on matching scalar
keys. Lists become ordered unions with machine-local entries first, because replacing them
drops machine-local data that has no portable counterpart. Equal entries are carried once,
so repeated applies converge instead of growing the file.

This widens the documented contract from "portable values win on matching keys" to
"portable values win on matching scalar keys; list-valued keys accumulate". The narrower
rule cannot express coexistence with any other tool that installs hooks.

### Sandbox

The sandbox is enabled as a guardrail rather than a hard gate, matching this repository's
existing posture. `failIfUnavailable` stays false so a host without bubblewrap warns and
runs unsandboxed instead of refusing to start; `allowUnsandboxedCommands` stays true so a
command the sandbox breaks can be retried outside it under ordinary permission prompts.
`autoAllowBashIfSandboxed` keeps routine sandboxed work from prompting, which is what makes
the credential rules the meaningful signal rather than noise.

Network is an allowlist of the toolchain this repository actually depends on, with
`strictAllowlist` unset so an unlisted host prompts rather than fails. Instance-metadata
endpoints are denied unconditionally. Credential files and environment variables are denied
to sandboxed commands, with a deliberate exception for `gh` state: two skills in this
library drive `gh` directly and would break.

Path resolution for `sandbox.filesystem` and `sandbox.credentials` entries is relative to
`~/.claude` for user settings, not to the project, so per-project paths cannot be expressed
there. Per-project secrets stay the responsibility of the existing `permissions.deny`
rules.

### Planning routing

Claude Code exposes no setting that changes the model used by plan mode. The only built-in
variant is the `opusplan` alias, which pins Opus while planning and Sonnet at rest — the
inverse of what is wanted and not reconfigurable. Delegation is therefore the only
supported mechanism.

User-scope agent definitions override built-ins of the same name, so a repository-owned
`Plan` agent pinned to Fable covers delegation through the built-in name, and the existing
`planner` covers delegation through the portable name. `CLAUDE.global.md` gains a routing
rule so main sessions delegate planning instead of doing it inline, and still never switch
their own model.

The cost is that overriding a built-in replaces an upstream-maintained system prompt with a
repository-owned one that will not track upstream changes. This is accepted because the
alternative leaves the stated model routing unenforced whenever the built-in name is used.

## Component Changes

`scripts/sync_config.py` gains list-union merging and a `--carry` flag that folds unmanaged
settings into the overlay and rewrites it. `scripts/bootstrap.sh` and `scripts/bootstrap.ps1`
gain per-entry linking and the generated-output comparison. `scripts/doctor.sh` reports
sandbox dependencies per platform as optional rather than required, matching
`failIfUnavailable: false`.

Three vendored skills carry port defects that are corrected in place: an `agent_type` key
double-substituted into `subsubagent_type` in three dispatch templates, a truncated
platform list, and a skill description that still names Codex as the acting agent. The last
one is matched against during skill selection, so it degrades routing rather than only
reading badly.

## Safety and Local State

No credentials, authentication state, or generated settings enter Git. Apply remains
opt-in, and the dry run remains non-mutating. The new carry behavior writes to
`~/.claude/settings.local.json`, which is machine-local and already ignored.

Enabling the sandbox changes observable behavior: commands that read SSH or cloud
credentials now fail inside the sandbox and require an unsandboxed retry that prompts. This
is intended, and is the reason `allowUnsandboxedCommands` is not disabled.

## Verification

Verification covers the repository validator, the full native test suite, Bash syntax
checks, and a dry run against the real home directory. Beyond static checks, apply is
rehearsed end to end against a temporary home seeded to match a used machine: a foreign
skill, an unmanaged `settings.json` carrying a status line and third-party hooks, and a
populated overlay. That rehearsal asserts both layers of hooks survive, unmanaged keys are
preserved, and a second apply is byte-identical.

The sandbox block is validated against the running Claude Code build with `claude doctor`,
which reports schema-invalid settings keys as ignored fields. A clean report is the
evidence that every key is accepted, since invalid keys fail silently.

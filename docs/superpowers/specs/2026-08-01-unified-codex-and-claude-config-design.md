# Unified Codex and Claude Configuration

## Goal

Collapse `codex-config` and `claude-config` into one repository that installs a Codex
configuration, a Claude Code configuration, or both, from a single command. Keep one copy
of the shared skill library and one installer, and migrate the machine that already runs
the split layout without breaking its live installation.

## Why this is cheap now

The two repositories are one repository. `codex-config`'s HEAD is the merge base:
`claude-config` already contains all 83 of its commits and adds nine on top. A trial merge
of `codex-config` into `claude-config` reports "Already up to date".

Unification is therefore not a merge and has no content to reconcile. The port deleted the
Codex surfaces in a single commit; restoring them is a checkout of 35 paths from the
common ancestor. With both trees present the existing validator and test suite still pass
unchanged, because nothing collides: `.codex/` and `.claude/` are disjoint, the two global
instruction files have different names, the profile sets are distinguished by extension,
and the install targets `~/.codex` and `~/.claude` never overlap.

The window closes as the trees drift. The provider-specific skill files are where drift
concentrates, and three defects were already found there — a dispatch key double-rewritten
to `subsubagent_type`, a truncated platform list, and a description still naming Codex as
the acting agent. Those exist precisely because the file was hand-edited in a fork rather
than kept dual-provider.

## Architecture

### Layout

One repository holds both provider surfaces beside the shared library.

```
.codex/     config.toml, hooks.json, agents/*.toml, hooks/*.py
.claude/    settings.json, mcp.json, agents/*.md, hooks/*.py
AGENTS.global.md      CLAUDE.global.md
profiles/   *.config.toml (Codex)   *.mcp.json (Claude)
skills/     one copy, dual-provider prose, agents/openai.yaml restored
scripts/    install.sh, bootstrap.sh, sync_config.py, validate.py, doctor.sh
```

### Provider descriptor

The installers differ in more than a directory name, so a target is described rather than
branched on ad hoc. Each provider fixes: the CLI to probe, the home directory, the base
config and its format, the machine-local overlay name, the generated-output path, the
instruction file and its installed name, the set of linked directories, the skills
destination, and how MCP servers are registered.

The two providers disagree on every one of those. Codex installs skills to
`~/.agents/skills` rather than under its own home, links `hooks.json` and the profile files
into `~/.codex`, and declares MCP servers inside `config.toml`. Claude Code installs skills
to `~/.claude/skills`, has no `hooks.json`, and registers MCP servers through its CLI.

In shell this is a `TARGET` variable and a small set of accessor functions rather than a
simulated object, because the fan-out is two and the accessors stay readable.

### Target selection

`scripts/install.sh --target codex|claude|both`. With no flag, the target is inferred from
which CLIs are on `PATH`: both present installs both, one present installs that one, none
present fails in preflight naming what to install. Inference is reported before it acts, so
a machine that grows a second CLI later does not silently change what an unchanged command
installs.

### Configuration merging

`sync_config.py` dispatches on file extension: `tomllib` and the existing TOML renderer for
`.toml`, `json` for `.json`. Merge semantics are format-independent and shared — recursive
object merge with portable values winning on scalar keys, ordered-union for lists, and the
`--carry` fold of unmanaged settings into the machine-local overlay.

Codex gains the list-union and carry behavior that Claude Code already has. This is not
incidental: `agent-session` installs hooks into both harnesses, so the array-replacement
defect that silently dropped a `SessionStart` handler on the Claude side exists identically
on the Codex side. The Codex merger's `runtime_overlay` special case for retaining
harness-written `hooks` keys is subsumed by `--carry`, which preserves any unmanaged key
rather than an enumerated list.

### Migration of a live split installation

This is the part that is not a file move. The machine already runs Codex from the old
repository, and `~/.codex/AGENTS.md`, `~/.codex/agents`, `~/.codex/hooks`,
`~/.codex/hooks.json`, and `~/.agents/skills` all point into `codex-config`. Stale
`.pre-move` links from an earlier relocation sit beside them, so this failure recurs.

`link_item` currently treats a symlink pointing anywhere other than the expected source as
a conflict and refuses, which means the unified repository cannot install over the split
layout at all. Adoption is therefore explicit: `--adopt` repoints a link whose current
target resolves inside a known predecessor repository, reporting each repoint. Links
pointing somewhere unrecognized stay conflicts. Without `--adopt` nothing is repointed and
the conflict is reported with the exact command that would resolve it.

Per-entry linking already replaces whole-directory linking on the Claude side and is
extended to Codex, which needs it more: `~/.agents/skills` is a directory other tools write
into.

### Shared skills

The provider-specific skill files return to carrying both provider forms in one file. This
is the upstream Superpowers shape, not an invention — those files already ship
`Codex named custom-agent form:` beside `Claude Code general-purpose fallback:` and
per-platform tool references. The port stripped one side; restoring it removes the reason
the files drift.

Most divergence is a wording substitution rather than a structural difference: of the
twenty modified skill files, most differ by a single line naming the acting agent. The
substantive ones are the dispatch templates, `subagent-driven-development/SKILL.md`,
`requesting-code-review/code-reviewer.md`, and parts of `impeccable`.

## Naming

The repository is provider-neutral once unified, and its current name and path assert
otherwise. Renaming the checkout is a separate, reversible step taken after the contents
are verified, because every installed entry is a symlink into the checkout and moving it
invalidates all of them. The rename is therefore performed by reinstalling rather than by
moving the directory underneath a live installation.

## Safety and Local State

No credentials or generated state enter Git. Apply stays opt-in, the dry run stays
non-mutating, and adoption stays behind an explicit flag. Because the machine has a live
Codex installation, verification must confirm that a dry run reports the exact repoints it
would make and that refusing to adopt leaves the existing installation working.

## Verification

Beyond the validator and test suite, verification rehearses three installs against
temporary home directories: Codex only, Claude only, and both, each asserting the correct
link set and that the other provider's home is untouched. A fourth rehearsal seeds a home
with the live split layout — links pointing into a predecessor repository — and asserts
that the default run refuses with an actionable message and that `--adopt` repoints exactly
those links and nothing else.

The existing rehearsals are retained: coexistence with foreign discovery entries, survival
of third-party hooks through the merge, and byte-identical idempotency on a second apply.

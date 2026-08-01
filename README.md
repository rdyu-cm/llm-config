# Portable Claude Code Config

An audited, repository-contained Claude Code setup for implementation, planning, debugging, review, frontend work, browser automation, and security analysis.

The repository is the source of truth. Bootstrap is a non-mutating dry run by default. Apply mode installs merged user settings, links instructions/agents/hooks/skills into Claude Code's global discovery paths, and registers portable MCP servers through the Claude CLI. Existing unmanaged files are reported as conflicts rather than overwritten.

Agents and skills are linked entry by entry rather than as whole directories, because Claude Code discovers both by name inside directories that other tools also install into. A neighbour this repository does not own is left untouched instead of blocking the install.

## Quick start

Claude Code is intentionally not installed by this repository. Install it first, then:

```bash
# Preflight prerequisites, validate, apply, and verify the result.
./scripts/install.sh

# Or see what would change without touching your home directory.
./scripts/install.sh --dry-run
```

The individual steps remain available: `./scripts/doctor.sh` for an environment report, `./scripts/bootstrap.sh` for a dry run, and `./scripts/bootstrap.sh --apply` to apply. On Windows PowerShell, use `./scripts/bootstrap.ps1` and `./scripts/bootstrap.ps1 -Apply`; there is no PowerShell equivalent of `install.sh`.

### Onto a new machine

The installed entries are symlinks into this repository, so the clone is a permanent dependency rather than a staging directory. Put it somewhere durable and identical across machines if you want the paths to match.

```bash
git clone <remote> ~/claude/claude-config && ~/claude/claude-config/scripts/install.sh
```

Requirements: Python 3.11 or newer (the validator imports `tomllib`), the Claude Code CLI, and Git. Node and `npx` are needed only for the `codebase_memory` MCP server. On Linux, `bubblewrap` and `socat` enable the sandbox; without them Bash commands run unsandboxed and the install still succeeds.

Set `PYTHON` to select an interpreter when the default `python3` is older than 3.11:

```bash
PYTHON=/usr/bin/python3.11 ./scripts/install.sh
```

## Layout

- `CLAUDE.global.md`: compact personal defaults linked to `~/.claude/CLAUDE.md`.
- `CLAUDE.md`: instructions for maintaining this repository.
- `.claude/settings.json`: portable settings, permissions, and lifecycle hooks.
- `.claude/agents/`: Claude Code subagents with native Markdown/YAML frontmatter.
- `.claude/hooks/`: deterministic safety and session-context hooks.
- `.claude/mcp.json`: audited MCP source manifest used by bootstrap.
- `skills/`: canonical vendored Agent Skills library.
- `profiles/`: optional Claude settings overlays.
- `sources.lock.toml` and `plugins.lock.toml`: audited upstream revisions and rationale.
- `scripts/`: dry-run-first bootstrap, validation, health checks, and update checks.

## Models

Main sessions and named agents use `claude-opus-5` by default. Five explicitly difficult roles use `claude-fable-5`: `planner`, `Plan`, `implementer-deep`, `reviewer-deep`, and `security-reviewer`.

`Plan` overrides Claude Code's built-in planning subagent, so planning delegated through either the built-in name or the portable `planner` name runs on Fable. Main sessions are still never instructed to switch their own model; `CLAUDE.global.md` routes planning work to those agents instead. Claude Code has no setting that changes the model used by plan mode itself — the only built-in variant is the `opusplan` alias (Opus while planning, Sonnet otherwise), which cannot express Opus-resting plus Fable-planning — so delegation is the supported mechanism.

## MCP servers

Bootstrap registers these at user scope:

- `context7`: current third-party library documentation.
- `codebase_memory`: pinned to `codebase-memory-mcp@0.8.1`.
- `github`: registered only when `GITHUB_PAT_TOKEN` is set.

Anthropic product documentation is researched through Claude Code's web tools and official Anthropic domains; there is no fabricated OpenAI-to-Anthropic MCP substitution.

## Profiles

Launch one with `claude --strict-mcp-config --mcp-config profiles/<name>.mcp.json` to use only that profile’s MCP servers for the session.

## Sandbox

`sandbox.enabled` puts Bash commands inside Claude Code's OS-level sandbox — the counterpart to Codex's `sandbox_mode = "workspace-write"`, and a real boundary rather than a pattern match. Linux and WSL2 need `bubblewrap` (and `socat` for network filtering); macOS and native Windows are supported directly.

- `failIfUnavailable` stays `false`, so a host without the dependencies warns and runs unsandboxed instead of refusing to start. Portability wins over a hard gate here; set it to `true` on a machine where sandboxing is mandatory.
- `allowUnsandboxedCommands` stays `true`, so a command that a sandbox restriction breaks can be retried outside it and falls back to ordinary permission prompts.
- `autoAllowBashIfSandboxed` lets sandboxed commands run without prompting. Combined with the credential rules below, routine work stays quiet and credential-touching work surfaces a prompt.
- `network.allowedDomains` covers the toolchain this repository actually uses. `strictAllowlist` is deliberately unset, so an unlisted host prompts rather than failing outright. `deniedDomains` blocks the cloud instance-metadata endpoints unconditionally.
- `credentials.files` and `credentials.envVars` deny sandboxed commands access to SSH, GPG, cloud, registry, and Claude Code's own OAuth token. `gh` credentials are intentionally not denied, because two skills in this library drive `gh` directly.

Known Linux limitation: glob patterns in `Read(...)`/`Edit(...)` permission rules are dropped when they are translated into sandbox filesystem rules, so the `Read(./.env.*)` deny narrows to the sandbox-independent permission check on Linux. `claude doctor` reports this. Non-glob rules and everything in `sandbox.filesystem` are unaffected.

## Hooks

- `session_context.py` injects one compact reminder about verification and graph discovery.
- `command_policy.py` blocks only catastrophic host commands.
- `secret_guard.py` rejects Claude `Edit`/`Write` payloads that target likely credential files or add recognizable private keys and tokens.

Hooks are guardrails, not a complete security boundary. The sandbox, Claude Code permissions, and user confirmation remain the primary controls.

## Cross-session coordination

Waiting for other Codex or Claude sessions, queueing writers, leases, heartbeats, stale-lock recovery, fairness, and wakeups belong in a separate shared harness. A skill can request cooperation but cannot enforce reliable cross-process scheduling, so this repository intentionally does not claim to provide it.

## Secrets and generated state

Never commit credentials, Claude authentication state, `~/.claude.json`, transcripts, caches, MCP OAuth data, project trust, or generated settings. Machine-local settings belong in `~/.claude/settings.local.json`.

Merge rules, portable over machine-local:

- Objects merge recursively and portable values win on matching scalar keys.
- Lists are combined as ordered unions, machine-local entries first. Replacing them would drop machine-local data that has no portable counterpart — an unrelated `hooks.SessionStart` handler, or an accumulated `permissions.allow` list. Equal entries are carried once, so repeated applies do not grow the file.
- Anything in `~/.claude/settings.json` that this repository did not generate is folded into the machine-local overlay before the merge, instead of being discarded. Apply recognizes its own previous output by comparing against `.claude/settings.generated.json`, so portable values are never baked into the overlay. Both files existing is normal, not a conflict: Claude Code writes each of them on its own.

## Verification

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap.sh scripts/doctor.sh scripts/update.sh
./scripts/bootstrap.sh
./scripts/doctor.sh
```

Runtime `claude` verification requires Claude Code to be installed and is deliberately deferred until then.

## License

Original content is licensed under the [MIT License](LICENSE). Bundled third-party components retain their accompanying licenses and notices.

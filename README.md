# Portable Claude Code Config

An audited, repository-contained Claude Code setup for implementation, planning, debugging, review, frontend work, browser automation, and security analysis.

The repository is the source of truth. Bootstrap is a non-mutating dry run by default. Apply mode installs merged user settings, links instructions/agents/hooks/skills into Claude Code's global discovery paths, and registers portable MCP servers through the Claude CLI. Existing unmanaged files are reported as conflicts rather than overwritten.

## Quick start

Claude Code is intentionally not installed by this repository.

```bash
# Inspect planned changes; does not modify your home directory.
./scripts/bootstrap.sh

# Validate the repository and local prerequisites.
./scripts/doctor.sh

# After installing Claude Code and reviewing conflicts:
./scripts/bootstrap.sh --apply
```

On Windows PowerShell, use `./scripts/bootstrap.ps1` for a dry run and `./scripts/bootstrap.ps1 -Apply` to apply.

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

Named agents use `claude-opus-5` by default. Four explicitly difficult roles use `claude-fable-5`: `planner`, `implementer-deep`, `reviewer-deep`, and `security-reviewer`. Main sessions are not instructed to switch to Fable automatically.

## MCP servers

Bootstrap registers these at user scope:

- `context7`: current third-party library documentation.
- `codebase_memory`: pinned to `codebase-memory-mcp@0.8.1`.
- `github`: registered only when `GITHUB_PAT_TOKEN` is set.

Anthropic product documentation is researched through Claude Code's web tools and official Anthropic domains; there is no fabricated OpenAI-to-Anthropic MCP substitution.

## Profiles

Launch one with `claude --strict-mcp-config --mcp-config profiles/<name>.mcp.json` to use only that profile’s MCP servers for the session.

## Hooks

- `session_context.py` injects one compact reminder about verification and graph discovery.
- `command_policy.py` blocks only catastrophic host commands.
- `secret_guard.py` rejects Claude `Edit`/`Write` payloads that target likely credential files or add recognizable private keys and tokens.

Hooks are guardrails, not a complete security boundary. Claude Code permissions and user confirmation remain primary controls.

## Cross-session coordination

Waiting for other Codex or Claude sessions, queueing writers, leases, heartbeats, stale-lock recovery, fairness, and wakeups belong in a separate shared harness. A skill can request cooperation but cannot enforce reliable cross-process scheduling, so this repository intentionally does not claim to provide it.

## Secrets and generated state

Never commit credentials, Claude authentication state, `~/.claude.json`, transcripts, caches, MCP OAuth data, project trust, or generated settings. Machine-local settings belong in `~/.claude/settings.local.json`; portable values win on matching keys.

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

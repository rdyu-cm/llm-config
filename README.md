# LLM Config for Codex and Claude Code

An audited, portable configuration for **OpenAI Codex and Anthropic Claude Code**. It
provides one shared skill library plus provider-specific agents, settings, hooks, MCP
servers, model routing, sandbox policy, and installation paths. Use either provider on its
own or install both from the same checkout.

The repository is the source of truth. Bootstrap is a non-mutating dry run by default. Apply mode installs a merged config per provider, links instructions, agents, hooks, and skills into that provider's discovery paths, and registers MCP servers the way that provider expects. Existing unmanaged files are reported as conflicts rather than overwritten.

Agents and skills are linked entry by entry rather than as whole directories, because both providers discover them by name inside directories that other tools also install into. A neighbour this repository does not own is left untouched instead of blocking the install.

## Quick start

Neither Codex nor Claude Code is installed by this repository. Install at least one CLI,
then clone this repository into a durable location because the installed entries are
symlinks back to the checkout:

```bash
git clone https://github.com/rdyu-cm/llm-config.git ~/llms/llm-config
cd ~/llms/llm-config

# Install one provider or both.
./scripts/install.sh --target codex
./scripts/install.sh --target claude
./scripts/install.sh --target both

# Alternatively, infer the target from whichever CLIs are currently on PATH.
./scripts/install.sh

# See what would change without touching your home directory.
./scripts/install.sh --dry-run
```

With no `--target`, the providers are inferred from the CLIs on `PATH` and the inference is printed before anything happens, so a machine that gains a second CLI later does not silently change what an unchanged command installs.

The individual steps remain available: `./scripts/doctor.sh` for an environment report and `./scripts/bootstrap.sh [--apply] [--target ...]` for the install itself. On Windows PowerShell, use `./scripts/bootstrap.ps1`; it targets Claude Code only, and there is no PowerShell equivalent of `install.sh`.

### Migrating from the split repositories

This configuration was previously two repositories, and an existing machine has links pointing into whichever one it installed. Those are reported as adoptable, and nothing is repointed without asking:

```bash
./scripts/install.sh --dry-run          # lists what would be adopted
./scripts/install.sh --adopt            # repoints them
```

A link is adoptable only when it points into a predecessor checkout of this same configuration. Anything else stays a conflict and is left alone. An older whole-directory link, such as `~/.agents/skills`, is replaced by per-entry links rather than followed.

### Onto a new machine

The installed entries are symlinks into this repository, so the clone is a permanent dependency rather than a staging directory. Put it somewhere durable and identical across machines if you want the paths to match.

For a clean machine with both CLIs installed, the explicit command is
`~/llms/llm-config/scripts/install.sh --target both`. Use `--adopt` only when migrating
links created by the predecessor repositories; a clean machine does not need it.

Requirements: Python 3.11 or newer (the validator imports `tomllib`), at least one of the Codex or Claude Code CLIs, and Git. Node and `npx` are needed only for the `codebase_memory` MCP server. On Linux, `bubblewrap` and `socat` enable the sandbox; without them Bash commands run unsandboxed and the install still succeeds. `./scripts/doctor.sh` names whichever is missing and prints the install command for the detected package manager; installing it is left to you, because that is the one step needing root.

Set `PYTHON` to select an interpreter when the default `python3` is older than 3.11:

```bash
PYTHON=/usr/bin/python3.11 ./scripts/install.sh
```

### GitHub CLI (optional)

Some review and CI skills use GitHub's `gh` CLI. Install `gh` separately using the
[official platform instructions](https://github.com/cli/cli#installation), then authenticate
it without placing a token in this repository:

```bash
gh auth login --hostname github.com --git-protocol ssh --web
gh auth status
```

Recent versions of `gh` also publish an optional skill that teaches supported coding agents
how to drive the CLI. User scope is recommended because the CLI is useful across repositories:

```bash
gh skill install cli/cli gh --scope user
```

This command installs agent instructions, not the `gh` executable, and therefore only works
after the CLI itself is installed. Update the skill independently with `gh skill update gh`.

## Layout

Shared:

- `CLAUDE.md`: instructions for maintaining this repository.
- `skills/`: the canonical vendored skill library, one copy serving both providers.
- `capability-bundle.toml`: catalog of every component, with a `provider` key on the provider-specific ones.
- `sources.lock.toml` and `plugins.lock.toml`: audited upstream revisions and rationale.

Claude Code:

- `CLAUDE.global.md` linked to `~/.claude/CLAUDE.md`.
- `.claude/settings.json`, `.claude/mcp.json`, `.claude/agents/*.md`, `.claude/hooks/`.
- `profiles/*.mcp.json`.

Codex:

- `AGENTS.global.md` linked to `~/.codex/AGENTS.md`.
- `.codex/config.toml`, `.codex/hooks.json`, `.codex/agents/*.toml`, `.codex/hooks/`.
- `profiles/*.config.toml`. Skills are published to `~/.agents/skills`.

`scripts/` holds the dry-run-first installer, bootstrap, validation, health checks, and update checks.

## Workflows and skills

Skills are selected when their descriptions match the task; they are not all run for every
request. The usual development path is:

| Stage | Workflow |
| --- | --- |
| Understand | `brainstorming` resolves material design choices; `writing-plans` turns an approved design into executable steps. |
| Isolate | `using-git-worktrees` protects the current branch before tracked changes. |
| Implement | `test-driven-development` drives focused changes; `executing-plans` or `subagent-driven-development` handles approved multi-step work. |
| Diagnose | `systematic-debugging` reproduces failures and identifies causes before fixes; `playwright` captures browser evidence. |
| Review | `requesting-code-review`, `receiving-code-review`, and the reviewer agents check correctness, risk, and feedback. |
| Verify and finish | `verification-before-completion` requires fresh evidence; `finishing-a-development-branch` offers merge, PR, keep, or cleanup choices. |

The installed skill library is grouped below. Shared skills include provider-specific
guidance where the two CLIs differ.

### Development and maintenance

- `brainstorming`: clarify requirements and consequential design choices.
- `writing-plans`: produce a file-oriented implementation plan from an approved design.
- `executing-plans`: execute a written plan with review checkpoints.
- `subagent-driven-development`: coordinate independent implementation slices when delegation is requested.
- `test-driven-development`: establish failing coverage before feature or bug-fix code.
- `unit-test-design`: choose the behavior, inputs, and assertions that make a unit test able to fail.
- `systematic-debugging`: reproduce unexpected behavior and isolate its cause.
- `using-git-worktrees`: create an isolated branch workspace for tracked changes.
- `verification-before-completion`: require fresh test, lint, type, or smoke-check evidence.
- `finishing-a-development-branch`: guide local merge, pull request, preservation, or cleanup.
- `project-health`: run and report a repository's native verification suite without modifying it.
- `explain-as-you-go`: add concise teaching commentary when explicitly requested.
- `modern-python`: configure Python projects around `uv`, Ruff, and ty.
- `cli-creator`: turn APIs, specifications, or scripts into composable command-line tools.

### Review, GitHub, and security

- `requesting-code-review`: request a structured final review before integration.
- `receiving-code-review`: validate review feedback before applying it.
- `differential-review`: security-focused review of commits, diffs, and blast radius.
- `gh-address-comments`: inspect and address comments on the current GitHub pull request.
- `gh-fix-ci`: diagnose GitHub Actions failures and propose a fix before editing.
- `agentic-actions-auditor`: find prompt-injection paths and unsafe permissions in AI-enabled Actions workflows.
- `insecure-defaults`: detect fail-open configuration, weak authentication, and embedded secrets.
- `sharp-edges`: identify APIs and configuration designs that are easy to misuse.
- `supply-chain-risk-auditor`: assess dependencies for takeover and ecosystem risk.
- `property-based-testing`: strengthen parsers, validation, serialization, and invariant-heavy code with generated tests.

### Frontend and browser work

- `impeccable`: design or audit frontend UX, visual hierarchy, accessibility, responsiveness, and polish.
- `playwright`: automate real browser flows, screenshots, traces, and data extraction.
- `vercel-react-best-practices`: improve React and Next.js performance and data-loading patterns.
- `vercel-composition-patterns`: build scalable React APIs with composition instead of proliferating flags.

### Scientific research

- `scientific-research`: synthesize primary literature, authoritative datasets, and standards with citations.
- `research-eval`: design reproducible benchmarks, metrics, comparisons, and uncertainty analysis.
- `research-memory`: preserve inspectable sources, experiments, decisions, negative results, and handoffs.
- `research-compact`: create evidence-linked continuation records before context loss or handoff.
- `scientific-ml`: run hypothesis-driven ML experiments with provenance, leakage controls, baselines, ablations, and reproducible artifacts.

## ECC provenance and updates

Five shared skills adapt a narrow, audited subset of ECC for both providers without
installing ECC's plugin, agents, commands, hooks, rules, dashboard, memory runtime, or MCP
servers. Their user-facing descriptions are listed above.

ECC is pinned in `sources.lock.toml`. The normal update check reports when that repository
moves. To inspect only changes under the five upstream workflows used by these adaptations:

```bash
scripts/update.sh --review ecc
```

The review uses a temporary Git repository and never applies updates automatically. Inspect
the upstream diff, adapt relevant changes locally, run verification, and update the pin
manually.

## Models

Claude Code main sessions default to `claude-opus-5` at high reasoning effort
(`effortLevel: high`). Planning switches to Fable: the `Plan` and `planner` agents pin
`claude-fable-5` and inherit the session's high effort. The other non-implementation named
agents also use `claude-fable-5`, and the four file-modifying roles use `claude-opus-5`:
`implementer`, `implementer-fast`, `implementer-standard`, and `implementer-deep`.

`Plan` overrides Claude Code's built-in planning subagent, so planning delegated through either the built-in name or the portable `planner` name switches to Fable. Main sessions do not switch models in place: `CLAUDE.global.md` routes planning to a Fable agent and approved file-modifying work to an Opus implementer while the main session coordinates and verifies it. Claude Code has no setting that changes the model used by plan mode itself (the built-in `opusplan` alias is a fixed Opus/Sonnet pairing), so named-agent delegation is the supported routing mechanism.

Codex main sessions inherit the model selected by the installed Codex CLI. Named planning,
review, and security agents use `gpt-5.6-sol`; routine implementers use `gpt-5.6-terra`,
while `implementer-deep` uses `gpt-5.6-sol`.

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

Never commit credentials, authentication state (`~/.claude.json`, `~/.codex/auth.json`), transcripts, caches, MCP OAuth data, project trust, or generated configs. Machine-local settings belong in `~/.claude/settings.local.json` and `~/.codex/config.local.toml`.

Claude Code stores settings as JSON and Codex as TOML. `scripts/sync_config.py` dispatches load and render on the file extension; the merge rules below are shared by both.

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

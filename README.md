# Portable Codex Config

An audited, repository-contained Codex setup for implementation, planning, debugging, review, frontend work, browser automation, and security analysis.

The repository is the source of truth. `scripts/bootstrap.sh` links it into Codex's global discovery paths without copying secrets or silently discarding an existing setup. On first install, an existing `~/.codex/config.toml` becomes the machine-local overlay at `~/.codex/config.local.toml`. The tracked portable base overrides matching local keys, and the generated merged file stays ignored by Git.

## Quick start

```bash
# Inspect what would be linked; this does not change your home directory.
./scripts/bootstrap.sh

# Validate the repository itself.
./scripts/doctor.sh

# After reviewing conflicts, install links globally.
./scripts/bootstrap.sh --apply
```

On Windows PowerShell, use `./scripts/bootstrap.ps1` for a dry run and `./scripts/bootstrap.ps1 -Apply` to create links. Creating symbolic links may require Developer Mode or an elevated shell.

Restart Codex after applying the bootstrap. Open `/hooks` once to review and trust the exact hook definitions, then use `/mcp` to inspect active MCP servers.

## Layout

- `AGENTS.global.md`: compact personal behavior defaults.
- `AGENTS.md`: instructions for maintaining this repository itself.
- `skills/`: canonical, vendored skill library.
- `.agents/skills`: repo-local discovery link to `skills/`.
- `.codex/config.toml`: tracked portable defaults and MCP definitions.
- `.codex/config.generated.toml`: ignored merged output used by Codex after bootstrap.
- `.codex/agents/`: narrow custom agents and Superpowers model tiers.
- `.codex/hooks.json` and `.codex/hooks/`: deterministic lifecycle guardrails.
- `profiles/`: minimal, frontend, security, and full configuration overlays.
- `sources.lock.toml`: audited upstream commits and licenses.
- `plugins.lock.toml`: records why Superpowers is vendored selectively instead of enabled as a plugin.
- `scripts/`: safe bootstrap, validation, health checks, and update checks.

## Installed skills

### OpenAI

- `cli-creator`: designs composable, agent-friendly command-line tools with safe auth and JSON contracts.
- `gh-address-comments`: reads and resolves GitHub pull-request review comments through `gh`.
- `gh-fix-ci`: inspects GitHub Actions failures and implements an approved fix.
- `playwright`: token-efficient, CLI-first browser navigation, snapshots, screenshots, traces, and UI-flow debugging.

Current Codex releases already provide system skills such as `skill-creator`, `skill-installer`, `plugin-creator`, and `openai-docs`; they are not duplicated here.

### Superpowers workflow subset

- `brainstorming`: clarifies intent and design before creative implementation.
- `writing-plans`: produces implementation-ready plans for multi-step changes.
- `test-driven-development`: applies red-green-refactor to features and bug fixes.
- `systematic-debugging`: traces root causes before changing code.
- `verification-before-completion`: requires fresh command evidence before success claims.
- `requesting-code-review`: prepares completed work for structured review.
- `receiving-code-review`: evaluates review feedback technically before applying it.
- `finishing-a-development-branch`: verifies completion and presents merge, PR, keep, or cleanup choices.
- `executing-plans`: executes written implementation plans with review checkpoints.
- `subagent-driven-development`: executes plan tasks with fresh implementer and reviewer subagents.
- `using-git-worktrees`: creates or verifies isolated workspaces before plan execution.

The full Superpowers plugin is not enabled. Its global bootstrap, mandatory workflow, delegation, and worktree behavior would be disproportionate for many small tasks.

### Frontend

- `impeccable`: complete Codex-specific frontend design, critique, accessibility, responsive, motion, hardening, and visual iteration workflow.
- `vercel-react-best-practices`: React and Next.js performance rules prioritized by impact.
- `vercel-composition-patterns`: scalable React component API and composition patterns.

### Security and testing

- `differential-review`: security-focused review of a code change and its history.
- `insecure-defaults`: detects fail-open configuration, weak authentication, and embedded credentials.
- `sharp-edges`: finds dangerous APIs and misuse-prone configuration design.
- `property-based-testing`: designs generative tests and interprets shrinking/failures across languages.
- `supply-chain-risk-auditor`: assesses dependency health and takeover risk.
- `agentic-actions-auditor`: audits AI-powered GitHub Actions for prompt-injection and workflow risks.
- `modern-python`: current `uv`, Ruff, pytest, packaging, and Python project practices.

## MCP servers

Base configuration:

- `openaiDeveloperDocs`: enabled; authoritative OpenAI product and API documentation.
- `context7`: enabled; current third-party library documentation. `CONTEXT7_API_KEY` is optional and improves rate limits.
- `github`: configured against GitHub's hosted MCP endpoint but disabled until a least-privilege `GITHUB_PAT_TOKEN` is exported.
- `codebase_memory`: pinned to `codebase-memory-mcp@0.8.1` and enabled by default through `npx`. Minimal and frontend profiles disable it explicitly.

GitHub write-capable tools use the `writes` approval mode. Do not commit PATs or enable GitHub MCP without reviewing token scopes.

## Profiles

After bootstrap, run Codex with:

```bash
codex --profile minimal
codex --profile frontend
codex --profile security
GITHUB_PAT_TOKEN=... codex --profile full
```

- `minimal`: disables every MCP for the fastest local session.
- `frontend`: enables docs MCPs and relies on the Playwright skill rather than a browser MCP.
- `security`: enables docs and Codebase Memory, while keeping GitHub writes unavailable.
- `full`: additionally enables GitHub and Codebase Memory.

## Custom agents

- `reviewer`: read-only correctness, regression, security, and missing-test review.
- `docs_researcher`: read-only primary-source and version-sensitive API research.
- `browser_debugger`: reproduces browser behavior and writes only diagnostic artifacts.
- `security_reviewer`: read-only dispatcher for the narrow Trail of Bits review skills.
- `planner`: read-only planning role pinned to `gpt-5.6-sol`.
- `implementer`: bounded workspace-writing role pinned to `gpt-5.6-terra`.

The four specialist agents inherit the current model. Planner and implementer are intentionally
pinned for harness role routing; capability preflight must reject an unavailable pin rather than
silently substitute another model.

Superpowers implementation and review dispatches use five model-tier agents. Fast implementation
uses `implementer_fast`; integration work uses `implementer_standard`; broad design-sensitive work
uses `implementer_deep`; routine review uses `reviewer_standard`; subtle or whole-branch review uses
`reviewer_deep`. Their developer instructions stay intentionally thin so the complete Superpowers
task prompt remains unchanged.

## Harness capability catalog

`capability-bundle.toml` catalogs the portable instructions, profiles, skills, agents, hooks, MCP
definitions, and plugin pin that `codex-harness` may admit for a run. It contains paths and immutable
references only. Authentication, local overlays, generated config, hook trust state, caches, and
transcripts remain outside the bundle.

The catalog records `one_writer_per_worktree` as the default writer-isolation policy. The harness
serializes or rejects concurrent writers until its executor can allocate a separate disposable Git
worktree or clone for each one.

## Hooks

- `session_context.py`: injects one compact reminder about verification and graph discovery.
- `command_policy.py`: blocks only catastrophic host commands such as formatting disks, deleting filesystem roots, raw device writes, or shutting down the machine.
- `secret_guard.py`: rejects patches that create likely credential files or add recognizable private keys and token formats.

Hooks are not a complete security boundary. Codex also requires explicit trust for non-managed hooks, and the sandbox and approval policy remain the primary controls.

## Updating

```bash
./scripts/update.sh
```

The update check compares every pinned commit with upstream `HEAD` and exits nonzero when review is needed. It never replaces installed code. Review upstream changes and licenses, reinstall the selected paths with the Codex skill installer, run `./scripts/doctor.sh`, then update `sources.lock.toml`.

## Secrets and generated state

Keep credentials in environment variables or a local ignored `.env`. Do not add Codex authentication state, transcripts, MCP OAuth data, Codebase Memory indexes, caches, browser output, or local overrides to this repository.

Machine-specific model choices, project trust entries, and TUI state belong in `~/.codex/config.local.toml`. Codex-owned hook trust hashes remain in the ignored generated config and are preserved when it is regenerated. Re-run `./scripts/bootstrap.sh --apply` after pulling portable config changes; it regenerates the ignored merged config. Portable values win when both layers define the same key.

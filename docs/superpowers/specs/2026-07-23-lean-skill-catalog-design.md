# Lean Skill Catalog Design

## Objective

Return the portable Codex configuration to its pre-gstack architecture, retain independent reliability and routing improvements, and center the installed catalog on Superpowers plus selected technical skills. Add two small, neutral skills for learning-oriented explanations and project-native health checks. Do not copy or depend on gstack content.

## Baseline and preservation boundary

Commit `eadfa3c` is the last revision before gstack design or implementation. It defines the architectural baseline, not a literal rollback target. Later changes that are independent of gstack remain in place:

- the regular-file installation of `~/.codex/config.toml`, including migration from the former managed symlink;
- Codebase Memory configuration and bootstrap prewarming;
- the current model-specific agent catalog;
- portable profiles, hooks, and non-gstack source pins;
- standalone Playwright compatibility work;
- the general worktree-first and non-overlapping planning guidance.

Gstack-specific code, generated content, documentation, source metadata, tests, and routing are removed.

## Installed skill catalog

The existing 25 personal skills remain unchanged. They comprise the Superpowers workflow skills and focused technical, frontend, GitHub, and security skills already present before gstack. Their frontmatter descriptions and instructional bodies will not be compressed.

Two original skills are added:

### `explain-as-you-go`

An explicitly invoked teaching layer with three depths:

- `brief`: explain important decisions and unfamiliar concepts;
- `guided`: also explain control flow, assumptions, alternatives, and verification;
- `tutorial`: also include derivations or examples, prediction questions, and falsification checks.

The skill explains meaningful reasoning rather than narrating trivial commands. For scientific work it covers mathematical or physical interpretation, units and dimensions, numerical assumptions and stability, approximations and error sources, and why a test or experiment supports a conclusion. It prefers primary documentation and papers for external technical claims. If no depth is specified, it uses `guided`.

### `project-health`

A neutral project-native verification workflow. It discovers the repository's own formatter, linter, type checker, tests, and relevant static analysis, runs the smallest useful read-only checks first, and reports failures with exact evidence. It does not add a score, dashboard, telemetry, persona, new dependency, or replacement toolchain. It does not modify code unless the user separately requests fixes.

These are new prompts written for this repository. They do not copy gstack wording, structure, scripts, or runtime behavior.

## Skill-context budget

Removing the generated and directly exposed gstack skills eliminates the budget problem without editing the remaining descriptions. The currently exposed personal and system skill metadata outside gstack is approximately 2,676 tokens, or 1.04% of a 258,400-token context. The two concise additions should leave close to half of Codex's 2% skill-metadata allowance unused. Final verification will measure and report the resulting catalog; it will not add a permanent approximation of Codex's internal budgeting algorithm.

## Repository removal

Remove all gstack-owned artifacts:

- `vendor/gstack/` and `vendor/gstack-source.toml`;
- `generated/gstack-codex/` and `generated/gstack-codex-workflow/`;
- `gstack-capabilities.toml`;
- gstack preparation, installation, update, and notification scripts;
- gstack-specific test modules and assertions;
- gstack entries in `sources.lock.toml` and `capability-bundle.toml`;
- gstack sections in the README, global instructions, doctor, hooks, and bootstrap scripts;
- the obsolete gstack integration design and implementation-plan documents.

Mixed files are edited surgically. They are not reset wholesale to `eadfa3c`, because doing so would discard independent improvements.

## Installed-state migration

Users may already have links recorded in `~/.codex/gstack-managed.json`. Bootstrap will include a bounded one-time cleanup helper:

1. Read only a regular, non-symlink state file containing a version-1 object and a `links` object.
2. For each recorded target, remove it only when it is a symlink whose current resolved link text matches the recorded source exactly.
3. Never remove regular files, directories, unrecorded paths, or links changed by the user.
4. Remove the state file only after all safe recorded links have been handled. If unsafe or malformed state is encountered, stop with a conflict and preserve it for manual review.
5. In dry-run mode, report the actions without mutation.

The migration helper is repository-owned and contains no gstack prompt or runtime content. It exists solely to undo links created by earlier versions of this repository. Bootstrap runs it before installing the lean catalog so a single `--apply` leaves the live installation clean.

PowerShell receives equivalent cleanup behavior so supported bootstrap paths remain consistent.

## Routing policy

Remove the gstack subagent-routing section and every `gstack-*` planning route from `AGENTS.global.md`. Preserve these general rules:

- use `brainstorming` only for material product, architecture, interface, or behavior choices;
- use `writing-plans` for approved multi-step designs;
- do not run overlapping planning workflows by default;
- use isolated worktrees for tracked changes and obtain approval before merging to `main`.

`explain-as-you-go` activates only when explicitly requested. `project-health` activates for requests to assess repository health or run the complete native verification suite.

## Verification

Automated checks will cover:

- both new skills are registered, discoverable, and contain their required behavior;
- the capability catalog contains every personal skill and no gstack components;
- no tracked non-history file contains active gstack integration references;
- bootstrap accepts only its original action flags and retains config migration and Codebase Memory prewarming;
- a single bootstrap dry-run reports safe legacy-link cleanup without mutation;
- a single bootstrap apply removes only matching managed links and preserves conflicts;
- doctor no longer expects or reports a gstack runtime;
- source locks and update checks contain no gstack source;
- a verification-time estimate of installed skill metadata remains below 2% of 258,400 tokens;
- the complete Python unit suite, validation script, doctor smoke check, bootstrap dry-run, and whitespace check pass.

## Non-goals

- Reproducing gstack personas, product-review gauntlets, browser daemon, telemetry, memory system, deployment workflows, or shipping machinery.
- Compressing existing skill descriptions or instructional bodies.
- Removing any existing non-gstack personal skill.
- Merging the feature branch into `main` without explicit approval.

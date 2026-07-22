# Gstack Integration Design

**Date:** 2026-07-22
**Status:** Approved

## Goal

Integrate the upstream `garrytan/gstack` workflow into this portable Codex configuration while preserving this repository as the single clone and bootstrap entry point. The integration must keep gstack updateable, retain existing personal skills and model-pinned agents, and support both browser-free cluster installs and complete local-VM installs.

## Constraints

- One Git repository contains the portable configuration, personal capabilities, and pinned gstack source.
- One bootstrap command installs the selected capability set on a new machine.
- Vendored upstream source remains pristine; local policy and compatibility behavior live outside it.
- Gstack updates are explicit and reviewable, never automatic.
- Browser capabilities, Chromium, cookie handling, and the browser daemon are unavailable in cluster-oriented workflow installs.
- Existing user files, non-gstack links, dirty worktrees, and personal agent configuration are preserved.

## Source and Repository Layout

Vendor a complete, pristine snapshot of gstack under `vendor/gstack/`. Record its repository URL, exact commit, license, and installed items in `sources.lock.toml`. Preserve gstack's MIT license within the vendored directory.

Generated Codex-facing skill artifacts are kept outside the pristine vendor tree. Local bootstrap and routing code may consume upstream generators and templates, but no personal customization is patched directly into `vendor/gstack/`.

```text
codex-config/
├── .codex/agents/              personal model-pinned agents
├── generated/gstack-codex/     generated Codex-facing gstack skills
├── skills/                     personal and curated skills
├── vendor/gstack/              pristine pinned upstream snapshot
├── sources.lock.toml            upstream provenance and revision
└── scripts/                    bootstrap, checks, and update preparation
```

The generated directory is checked in so cluster bootstrap does not need to generate skill documentation. Runtime utilities used by workflow skills may still require Bun.

## Installation Profiles

Extend the existing bootstrap interface with an explicit gstack mode:

```bash
./scripts/bootstrap.sh --apply --gstack=off
./scripts/bootstrap.sh --apply --gstack=workflow
./scripts/bootstrap.sh --apply --gstack=full
```

`off` preserves the current installation behavior and exposes no gstack skills.

`workflow` exposes gstack's non-browser product discovery, planning, engineering and design review, code review, debugging, security, documentation, release, memory, retrospective, health, and safety workflows. It does not expose browser navigation, browser QA, live-site design review, scraping, cookie import, browser benchmarking, browser pairing, or browser-dependent deployment verification. Core skills with optional visual branches must use their existing no-browser fallback.

`full` exposes the complete Codex-compatible gstack catalog and installs its browser runtime, including Bun, Chromium, and the persistent local browser daemon.

Generated skills are linked under `~/.codex/skills/gstack-*`. Existing personal skills continue through this repository's `~/.agents/skills` discovery link. Bootstrap records which links it manages, and profile changes remove only stale gstack-managed links.

## Dependency Handling

Bun is required in both profiles because some workflow utilities use it. If Bun is absent, bootstrap installs a pinned Bun version using a downloaded installer whose checksum is recorded and verified before execution. A checksum mismatch or unavailable dependency aborts gstack setup before discovery links change.

Chromium and browser-specific dependencies are installed only in `full`. The `workflow` path must not download, build, launch, or advertise browser components.

Dry-run bootstrap reports required dependency and link changes without modifying the home directory. Apply mode validates prerequisites before mutation and rolls back only gstack-managed links created by the failing invocation.

## Workflow Ownership and Capability Overlap

Use gstack's workflow and skills unchanged where they already cover the task. Do not automatically chain overlapping personal skills into gstack. Keep personal capabilities discoverable for explicit use and add integration only when a demonstrated gap exists.

Gstack owns product discovery and its Think, Plan, Review, Test, Ship, and Reflect stages. This repository retains its specialized capabilities, including Codebase Memory, security-focused audits, property-based testing, modern Python guidance, React guidance, GitHub review and CI utilities, and portable Codex configuration.

Implementation after approval of a gstack plan remains owned by this repository's bounded execution workflow. The resulting changes return to gstack for review, QA when available, and shipping.

```text
gstack discovery and plan reviews
                ↓
       approved implementation plan
                ↓
 codex-config implementation agents
                ↓
       gstack review / QA / ship
```

## Subagent and Model Routing

Keep existing `.codex/agents/*.toml` files authoritative for model selection. Do not set Terra as the global unnamed-subagent default because strategic and design review benefit from the parent model.

Add one local routing policy that translates gstack's generic Agent-tool language into Codex agent selection while preserving the upstream subtask prompt verbatim:

| Gstack responsibility | Codex role |
| --- | --- |
| Routine or small code implementation | `implementer_fast` or `implementer` on `gpt-5.6-terra` |
| Multi-file integration implementation | `implementer_standard` on `gpt-5.6-terra` |
| Broad, design-sensitive implementation | `implementer_deep` on `gpt-5.6-sol` |
| Correctness or completion audit | `reviewer_standard` or `reviewer_deep` on `gpt-5.6-sol` |
| Security audit | `security_reviewer` on `gpt-5.6-sol` |
| Read-only code discovery | built-in `explorer` |
| Documentation-only write | `implementer_fast` on `gpt-5.6-terra` |
| No narrow match | `default`, inheriting the parent configuration |

When a generated gstack skill says to use the Agent tool with `subagent_type: general-purpose`, Codex must use its spawn-agent mechanism and select the narrowest matching role from this table. Gstack's deliberate second-opinion and cross-model calls remain review voices rather than implementation workers.

Initially rely on the routing policy rather than patching every generated skill. Add a narrow generation-time compatibility transform only if representative integration tests demonstrate that policy alone is insufficient.

## Updates

Extend the current source checker so `scripts/update.sh` reports whether the pinned gstack commit differs from upstream `main`.

Add `scripts/update-gstack.sh` as an explicit update-preparation command. It:

1. Queries upstream and reports pinned and candidate commits.
2. Downloads the candidate source into a temporary directory.
3. Verifies the downloaded revision.
4. Replaces only `vendor/gstack/`.
5. Regenerates Codex-facing skills.
6. Updates the gstack entry in `sources.lock.toml`.
7. Runs focused upstream and integration checks.
8. Leaves all changes uncommitted for human review.

The updater must not overwrite personal files or commit, push, or publish changes. Because the vendored tree is pristine, routine replacement should not require conflict resolution. Review remains mandatory because gstack has broad shell, Git, browser, cookie, deployment, and publishing capabilities.

## Startup Update Notification

Reuse `sources.lock.toml` as the only version source. The existing session-start hook performs a throttled gstack update check at most once every 24 hours. Cache status outside the repository under the user's normal cache directory.

When an update is available, startup prints a concise notice:

```text
update  gstack: a3259400a366 -> 84be2f97c419
        run ./scripts/update-gstack.sh
```

Fresh cache reads perform no network request. Expired checks have a strict timeout. Network, DNS, GitHub, or cache errors are silent and never block Codex startup. `CODEX_CONFIG_UPDATE_CHECK=0` disables the startup check. Bootstrap performs a fresh check and reports failure without failing installation.

The notification never modifies the vendored snapshot. Initially, "latest" means the commit at upstream `main`; stable release tags may replace that policy later if upstream establishes a reliable release channel.

## Safety and State Boundaries

- Browser skills, Chromium, cookies, remote pairing, and browser daemons exist only in `full`.
- Cookie import and remote pairing remain explicit gstack commands; setup never performs them automatically.
- Workflow mode must not leave stale browser skill links after switching from full mode.
- Gstack runtime state remains outside this repository and is ignored by Git.
- Update cache contains only public commit identifiers and timestamps, never credentials.
- Existing hooks, agents, personal skills, and machine-local overlays remain authoritative and are not rewritten by gstack setup.
- Gstack-managed link cleanup is constrained to recorded names and verified targets.

## Verification Strategy

Automated tests cover:

- Skill discovery for `off`, `workflow`, and `full`.
- The workflow allowlist excluding every browser-facing skill and runtime.
- The full profile exposing the complete supported gstack catalog.
- Repeated bootstrap and switching among profiles without duplicates or stale links.
- Preservation of personal skills, agents, overlays, and unrelated home-directory files.
- Temporary-`HOME` dry-run and apply behavior.
- Dependency preflight and rollback on failure.
- Terra and Sol role configuration remaining unchanged and routing policy availability.
- Vendored commit and MIT license consistency with `sources.lock.toml`.
- Update preparation leaving changes uncommitted.
- Startup cache freshness, update notices, opt-out, timeouts, malformed cache, and offline behavior.
- Running bootstrap from outside the repository.

Run gstack's free upstream tests that apply to the vendored revision. Do not make paid model evaluations or authenticated cookie tests part of the default suite. In environments with browser dependencies, add a full-profile smoke check for browser startup and health. Workflow-profile verification must succeed without Chromium.

## Success Criteria

- A new cluster can clone this repository and run one workflow-mode command without installing or exposing browser capabilities.
- A local VM can clone the same repository and run one full-mode command to receive the complete gstack workflow and browser runtime.
- Existing personal skills and Terra/Sol agent routing remain functional.
- Upstream gstack files remain pristine, pinned, licensed, and replaceable.
- Startup reports available gstack updates without automatically applying them or materially delaying offline use.

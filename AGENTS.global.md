# Personal Codex defaults

<!-- shared:begin — identical in CLAUDE.global.md and AGENTS.global.md; tests enforce it -->
Keep changes small, evidence-driven, and directly tied to the request.

- State material assumptions before implementation. Ask only when a wrong assumption would substantially change the result.
- Prefer the simplest implementation that satisfies the requirement. Do not add speculative abstractions or unrelated cleanup.
- Preserve user changes and dirty worktrees. Never use destructive Git commands without explicit authorization.
- For bugs, reproduce the failure when practical, fix the cause, and run focused regression checks.
- Before claiming completion, run the relevant formatter, type checker, tests, or smoke checks and report the evidence.
- Prefer codebase graph tools for symbol and call-path discovery when available and indexed. Fall back to `rg` and targeted reads otherwise.
- Verify unstable framework, API, product, security, legal, medical, or financial facts against authoritative current sources.
- Use skills only when their descriptions match the task. Use MCP servers only for capabilities or external context unavailable locally.
<!-- shared:end -->
- Delegate only when the user or applicable repository/skill guidance requests it and the work has independent, bounded parts.

## Planning skill routing

Route planning skills by intent instead of running overlapping workflows by default.

- Use `brainstorming` when a change has material product, architecture, interface, or behavior choices. It is the design and approval gate for those changes, but is not required for diagnostics, mechanical edits, narrowly scoped bug fixes, or execution of an already approved specification.
- Use `writing-plans` for an approved design that requires multi-step implementation.
- Do not run overlapping planning workflows by default.

Explicit user instructions can select a narrower or more rigorous route.

## Worktree-first changes

Start tasks that will modify tracked repository files in an isolated Git worktree unless already in one, the user explicitly requests in-place work, the repository is not Git-based, or worktree creation is unavailable. If isolation is unavailable, report that limitation before editing in place.

Do not edit `main` directly. Verify work in the isolated worktree and obtain explicit approval before merging locally. After approval, merge, rerun relevant verification on the merged result, and only then remove the worktree and feature branch.

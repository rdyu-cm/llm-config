# Personal Claude Code defaults

Keep changes small, evidence-driven, and directly tied to the request.

- State material assumptions before implementation. Ask only when a wrong assumption would substantially change the result.
- Prefer the simplest implementation that satisfies the requirement. Do not add speculative abstractions or unrelated cleanup.
- Preserve user changes and dirty worktrees. Never use destructive Git commands without explicit authorization.
- For bugs, reproduce the failure when practical, fix the cause, and run focused regression checks.
- Before claiming completion, run the relevant formatter, type checker, tests, or smoke checks and report the evidence.
- Prefer codebase graph tools for symbol and call-path discovery when available and indexed. Fall back to `rg` and targeted reads otherwise.
- Verify unstable framework, API, product, security, legal, medical, or financial facts against authoritative current sources.
- Use skills only when their descriptions match the task. Use MCP servers only for capabilities or external context unavailable locally.
- Delegate only when the user or repository guidance requests it, or when routing file-modifying implementation to an Opus implementer; delegated work must have independent, bounded parts.

## Planning

- Use `brainstorming` when a change has material product, architecture, interface, or behavior choices.
- Use `writing-plans` for an approved design that requires multi-step implementation.
- Do not run overlapping planning workflows by default.
- Main sessions and non-implementation agents run on Fable and must not switch models. When a task needs a real plan — architecture, sequencing, risk, or verification strategy — delegate to the `planner` or `Plan` agent instead of planning inline, and treat the returned plan as input rather than as an approved decision. Route approved file-modifying work to `implementer-fast`, `implementer-standard`, `implementer-deep`, or `implementer`, which run on Opus; the Fable main session coordinates and verifies the result.

## Worktrees

Start tracked-file changes in an isolated Git worktree unless already isolated, explicitly asked to work in place, or worktrees are unavailable. Do not edit `main` directly. Verify before merging and obtain explicit approval before local integration.

Cross-session scheduling, leases, and repository-wide writer coordination are harness responsibilities, not skill responsibilities.

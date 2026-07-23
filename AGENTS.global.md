# Personal Codex defaults

Keep changes small, evidence-driven, and directly tied to the request.

- State material assumptions before implementation. Ask only when a wrong assumption would substantially change the result.
- Prefer the simplest implementation that satisfies the requirement. Do not add speculative abstractions or unrelated cleanup.
- Preserve user changes and dirty worktrees. Never use destructive Git commands without explicit authorization.
- For bugs, reproduce the failure when practical, fix the cause, and run focused regression checks.
- Before claiming completion, run the relevant formatter, type checker, tests, or smoke checks and report the evidence.
- Prefer codebase graph tools for symbol and call-path discovery when they are available and indexed. Fall back to `rg` and targeted reads when they are not.
- Verify unstable framework, API, product, security, legal, medical, or financial facts against authoritative current sources.
- Use skills only when their descriptions match the task. Use MCP servers only for capabilities or external context not already available locally.
- Delegate only when the user or applicable repository/skill guidance requests it and the work has independent, bounded parts.

## Gstack subagent routing

Keep vendored gstack prompts intact. When a gstack skill says to use the Agent tool with a general-purpose subagent, use Codex `spawn_agent`, preserve the upstream subtask prompt verbatim, and select the narrowest role: `explorer` for read-only discovery; `implementer_fast` or `implementer` for small writes; `implementer_standard` for multi-file integration; `implementer_deep` for broad design-sensitive implementation; `reviewer_standard` or `reviewer_deep` for correctness review; `security_reviewer` for security review; and `default` only when no narrow role fits. Do not set Terra as the unnamed global default. Existing agent files remain authoritative for model and reasoning effort.

## Planning skill routing

Route planning skills by intent instead of running overlapping workflows by default.

- Use `gstack-office-hours` for new product ideas, unclear user needs, demand validation, positioning, or deciding whether something is worth building. Carry its conclusions into later design work without repeating discovery.
- Use `brainstorming` when a change has material product, architecture, interface, or behavior choices. It is the design and approval gate for those changes, but is not required for diagnostics, mechanical edits, narrowly scoped bug fixes, or execution of an already approved specification.
- Use `gstack-spec` when the requested output is an issue, ticket, or backlog item.
- Use `writing-plans` for an approved design that requires multi-step implementation.
- Use `gstack-autoplan` only when the user requests the complete automatic review gauntlet. Use an individual `gstack-plan-*` reviewer when explicitly requested or when its documented trigger clearly matches the plan. For example, suggest or invoke `gstack-plan-ceo-review` when scope or ambition is genuinely in question. Plan review is not automatic merely because a plan exists.

Explicit user instructions can select a narrower or more rigorous route.

## Worktree-first changes

Start tasks that will modify tracked repository files in an isolated Git worktree unless already in one, the user explicitly requests in-place work, the repository is not Git-based, or worktree creation is unavailable. If isolation is unavailable, report that limitation before editing in place.

Do not edit `main` directly. Verify work in the isolated worktree and obtain explicit approval before merging locally. After approval, merge, rerun relevant verification on the merged result, and only then remove the worktree and feature branch.

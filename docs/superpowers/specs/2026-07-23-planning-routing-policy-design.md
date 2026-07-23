# Planning and Worktree Routing Policy

## Goal

Eliminate ambiguity between personal planning skills and gstack planning skills, and keep tracked repository changes off `main` until they are verified and explicitly approved for integration.

## Planning precedence

Route planning work by intent:

1. Use `gstack-office-hours` for new product ideas, unclear user needs, demand validation, positioning, or deciding whether something is worth building. Its conclusions can seed a later design without repeating discovery.
2. Use `brainstorming` when a change has material product, architecture, interface, or behavior choices. It remains the design and approval gate for those changes, but is not required for diagnostics, mechanical edits, narrowly scoped bug fixes, or execution of an already approved specification.
3. Use `gstack-spec` when the requested output is an issue, ticket, or backlog item. It is not the default implementation-planning path.
4. Use `writing-plans` for approved designs that require multi-step implementation. It is the authoritative implementation-plan generator.
5. Use `gstack-autoplan` when the user requests the complete automatic review gauntlet. Use an individual `gstack-plan-*` reviewer when the user requests it or when its documented trigger clearly matches the plan. Reviews refine an existing plan; they do not replace discovery, design, or plan generation.

For example, `gstack-plan-ceo-review` may be suggested or invoked when the user questions a plan's scope or ambition, or the plan is visibly under-ambitious. It is not a mandatory review for every plan. Likewise, `gstack-autoplan` is not automatic merely because a plan exists.

This keeps every skill useful while assigning one owner to each planning stage and avoids running overlapping workflows by default. Explicit user instructions can select a narrower or more rigorous route.

## Worktree-first changes

Any task that will modify tracked repository files starts in an isolated worktree automatically.

Exceptions are limited to:

- the current workspace is already an isolated worktree;
- the user explicitly requests in-place work;
- the repository is not Git-based; or
- worktree creation is unavailable, in which case Codex reports the limitation before working in place.

Codex must not edit `main` directly. It verifies the implementation in the worktree, then asks for explicit approval before merging. After approval, it merges locally, reruns relevant verification on the merged result, and only then removes the worktree and feature branch.

## Scope

The policy belongs in `AGENTS.global.md`, alongside the existing personal defaults and gstack subagent routing. No skill files, generated gstack files, agent model definitions, or runtime behavior need to change.

## Verification

- Repository validation accepts the updated global instructions.
- Tests covering portable configuration continue to pass.
- The diff is limited to this design record and the global policy text.

# Planning and Worktree Routing Policy

## Goal

Eliminate ambiguity between personal planning skills and gstack planning skills, and keep tracked repository changes off `main` until they are verified and explicitly approved for integration.

## Planning precedence

Use the following sequence for implementation work:

1. `gstack-office-hours` is optional product discovery for new ideas, demand validation, positioning, and deciding whether something is worth building. Its output becomes input to the normal design process; it does not replace that process.
2. `brainstorming` is the mandatory design and approval gate before modifying repository behavior.
3. `writing-plans` is the authoritative implementation-plan generator after the design is approved.
4. `gstack-autoplan` or selected `gstack-plan-*` skills review an existing implementation plan after `writing-plans`; they do not replace the design or plan generators.
5. `gstack-spec` is reserved for issue, ticket, and backlog-item requests. It is not the default implementation-planning path.

This keeps every skill useful while assigning one owner to each planning stage. Explicit user instructions can select a narrower route, but implementation work still observes the mandatory design gate.

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

# Parent-Model Dispatch Fallback Design

## Goal

Keep active Codex subagent workflows operational when the surfaced
`spawn_agent` tool does not expose `agent_type`. Prefer configured custom roles
when native role selection exists, but otherwise dispatch a generic child that
inherits the parent model instead of stopping the workflow.

## Scope

Update active implementation and review workflow instructions, prompt-template
metadata, README guidance, and routing regression tests. Preserve standalone
custom-agent TOMLs and their Terra/Sol model pins so a future runtime with
native role selection can use them without another configuration migration.

## Dispatch Contract

Active Codex workflows choose between two explicit paths after inspecting the
available `spawn_agent` arguments.

When `agent_type` is available, dispatch the selected custom role with:

```text
spawn_agent(
  agent_type="<selected custom role>",
  fork_turns="none",
  task_name="<unique descriptive task label>",
  message="<self-contained task prompt>",
)
```

When `agent_type` is unavailable, dispatch through the surfaced generic form:

```text
spawn_agent(
  fork_turns="none",
  task_name="<unique descriptive task label>",
  message="<self-contained task prompt>",
)
```

The generic child inherits the parent model and reasoning effort. The workflow
must state this accurately in its own bookkeeping and must not claim that a
Terra/Sol custom-role pin was applied.

Both paths retain `fork_turns="none"` and a self-contained message. This keeps
task isolation consistent and avoids coupling generic fallback behavior to the
parent conversation history.

## Active Surfaces

- `skills/subagent-driven-development/SKILL.md` defines the capability check,
  preferred named-role path, and supported parent-model fallback.
- Its implementer and task-reviewer templates show named and generic Codex
  dispatch forms without changing the child prompt bodies.
- `skills/requesting-code-review/` applies the same fallback to standalone and
  final reviews.
- `README.md` describes role routing as preferred rather than required.
- Routing tests cover both forms, preserved prompt bodies, unique task names,
  and truthful fallback language.

## Failure Behavior

Missing `agent_type` alone is not a failure. Stop only when the surfaced tool
cannot perform the generic dispatch contract—for example, if `message`,
`task_name`, or `fork_turns="none"` is unavailable—or when spawning the generic
child itself returns an error.

The workflow must never substitute `task_name` as a role selector. It is only a
unique descriptive label in both paths.

## Verification

Add failing regression assertions that require generic parent-model fallback
and reject the previous stop-before-dispatch language. Then make the smallest
active-instruction and template changes needed to pass while preserving the
existing child-message hashes. Run the focused routing tests, the complete test
suite, bootstrap apply, and doctor.

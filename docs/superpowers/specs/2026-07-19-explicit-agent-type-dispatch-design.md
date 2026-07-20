# Explicit `agent_type` Dispatch Design

## Goal

Make every active Codex subagent workflow select custom agent roles through the
`spawn_agent` `agent_type` argument. Prevent instructions from implying that a
matching `task_name` selects a role or that model inheritance will apply the
role's configured model and reasoning effort.

## Scope

Update active workflow skills, dispatch prompt templates, user-facing README
guidance, and routing regression tests. Preserve historical plans and design
documents because they record earlier changes rather than drive current
dispatch behavior.

## Dispatch Contract

Every active instruction that dispatches a configured Codex role must require
the equivalent of:

```text
spawn_agent(
  agent_type="<selected custom role>",
  fork_turns="none",
  task_name="<descriptive task label>",
  message="<self-contained task prompt>",
)
```

`agent_type` is the only role selector. `task_name` remains a descriptive and
unique task label. `fork_turns="none"` permits the selected role's model and
reasoning configuration to differ from the parent; therefore the message must
carry all task context needed by the child.

The existing role files remain unchanged. They already define the intended
model routing, including Terra with medium reasoning for standard
implementation and Sol with high reasoning for deep implementation.

## Affected Surfaces

- `skills/subagent-driven-development/SKILL.md` defines the shared Codex
  dispatch contract and tier mapping.
- Its implementer and reviewer prompt templates require the selected role to be
  passed as `agent_type` with no history fork.
- `skills/requesting-code-review/` uses the same explicit reviewer dispatch
  contract.
- `README.md` documents the invocation rule alongside the tier overview.
- Routing tests assert that active instructions contain `agent_type`,
  `fork_turns`, and the distinction between role and task name.

## Failure Behavior

If the surfaced `spawn_agent` tool does not expose `agent_type` or
`fork_turns="none"`, the workflow must report that native role selection is
unavailable and stop before dispatch. It must not silently use `task_name`,
inherit the parent model, or claim that the configured Terra/Sol routing was
applied.

## Verification

Add the assertions first and confirm they fail against the current active
instructions. Then make the smallest documentation and prompt changes needed
to pass the focused routing tests. Run the full repository test suite and the
configuration doctor before completion.

# Superpowers Tiered Agent Routing Design

## Goal

Make the vendored Superpowers implementation and review workflows select an
appropriate Codex model for each delegated task without replacing or weakening
the upstream Superpowers task prompts.

## Design

Add five project custom agents under `.codex/agents/`:

| Agent | Model | Reasoning | Intended work |
| --- | --- | --- | --- |
| `implementer_fast` | `gpt-5.6-terra` | `medium` | Mechanical, well-specified changes touching one or two files |
| `implementer_standard` | `gpt-5.6-sol` | `medium` | Multi-file integration, debugging, and coordination |
| `implementer_deep` | `gpt-5.6-sol` | `high` | Implementation requiring broad context or design judgment |
| `reviewer_standard` | `gpt-5.6-sol` | `medium` | Small or routine task reviews |
| `reviewer_deep` | `gpt-5.6-sol` | `high` | Subtle, high-risk, or whole-branch reviews |

Each custom agent is a thin runtime layer. Its developer instructions define
only the stable role boundary: preserve unrelated work, obey the supplied task
contract, verify claims, and respect the configured read/write sandbox. The
agent file must not copy the detailed Superpowers prompt or introduce a second
workflow. At dispatch time, the complete existing Superpowers implementer or
reviewer prompt remains the unchanged source of task-specific requirements,
TDD steps, reporting, review criteria, and escalation behavior. The thin custom
agent layer supplies compatible runtime constraints without competing process
instructions.

The existing `planner` and `implementer` agents remain unchanged because they
are harness roles. Superpowers planning continues in the main thread through
`brainstorming` and `writing-plans`; no planner subagent is added to that flow.

## Skill Routing

Extend the Model Selection section of `subagent-driven-development` with the
concrete Codex agent mapping above. Its existing complexity signals choose the
tier:

- complete specification, isolated change, one or two files:
  `implementer_fast`;
- multi-file integration, pattern matching, or debugging:
  `implementer_standard`;
- broad architectural context or substantial design judgment:
  `implementer_deep`;
- small or routine task review: `reviewer_standard`;
- subtle, security-sensitive, concurrency-sensitive, or final whole-branch
  review: `reviewer_deep`.

If a worker reports that the task requires more reasoning, the controller
redispatches once at the next stronger implementer tier with the missing
context. It does not repeat the same underpowered dispatch unchanged.

Update the implementer, task-reviewer, and whole-branch reviewer dispatch
guidance to require a selected tier. The entire prompt body in each existing
template remains intact. On Codex, the controller selects the named custom
agent. On another supported platform, the existing general-purpose dispatch
continues to use that platform's explicit model selection mechanism. This
keeps the vendored workflow portable while making Codex routing enforceable.

Standalone `requesting-code-review` uses `reviewer_standard` by default and
selects `reviewer_deep` for broad, subtle, or high-risk changes. The final
whole-branch review from `subagent-driven-development` always uses
`reviewer_deep`.

## Failure Behavior

Pinned models must not be silently substituted. Capability preflight rejects a
requested tier whose model is unavailable. If a local Codex session cannot
discover a required custom agent, the workflow reports the missing agent and
stops before dispatch rather than inheriting the main session model
accidentally. Non-Codex platforms may use their existing explicit per-dispatch
model mechanism.

## Performance

The change does not increase the number of subagents, nesting depth, prompt
size in a material way, or write concurrency. Mechanical work moves to Terra;
integration and review stay on Sol; only difficult implementation and review
use high reasoning. The principal performance risk is under-classifying a
task and paying for a retry. The existing complexity signals and one-tier
escalation rule bound that risk.

Loading five small TOML files and validating their pinned models adds
negligible overhead. No new scheduler, agent loop, event stream, or persistence
state is added to `codex-harness`.

## Portability and Catalog

Add the five agents to `capability-bundle.toml` and the README inventory. The
existing bootstrap already links the entire `.codex/agents/` directory, so no
bootstrap change is required. `codex-harness` already validates admitted agent
model and reasoning fields and performs model capability preflight; its runtime
orchestration remains unchanged.

## Validation

Tests must verify:

- every tier agent has the exact model, reasoning effort, and sandbox;
- every catalog entry resolves to an existing agent TOML;
- active Superpowers implementation and review dispatch guidance names the
  appropriate tier and retains its original prompt body;
- the final whole-branch review selects `reviewer_deep`;
- unavailable pinned models continue to fail capability preflight rather than
  falling back;
- repository validation, focused unit tests, and the doctor check pass.

## Non-goals

- Do not make `codex-harness` a second subagent scheduler.
- Do not replace Superpowers prompts with custom-agent developer instructions.
- Do not add a planner subagent to brainstorming or plan writing.
- Do not change Superpowers task decomposition, review loops, report files, or
  write-isolation rules.
- Do not change the existing harness-specific `planner` and `implementer`
  agents.

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


# Enable Multi-Agent V2 by Default

## Goal

Make the portable Codex configuration start successfully with Multi-Agent V2
and preserve four concurrent child-agent slots.

## Design

Replace the legacy `agents.max_threads = 4` setting with a structured
`features.multi_agent_v2` configuration:

```toml
[features.multi_agent_v2]
enabled = true
max_concurrent_threads_per_session = 5
```

Multi-Agent V2 counts the root agent in its session-wide thread limit, so five
total threads preserve capacity for four children. Keep `agents.max_depth = 1`
and all named agent registrations unchanged. Existing Terra and Sol model pins
therefore continue to be selected by `agent_type`.

When Multi-Agent V2 is explicitly disabled, the legacy implementation will no
longer receive a portable `agents.max_threads` override and will use Codex's
own default concurrency limit.

## Verification

- Add a static regression assertion that the portable config enables V2 with
  five total threads and does not set `agents.max_threads`.
- Confirm the focused configuration test fails before the config change and
  passes afterward.
- Regenerate the installed merged config with `./scripts/bootstrap.sh --apply`.
- Confirm the installed CLI accepts the effective V2 configuration during TUI
  bootstrap without making a model request.
- Run the relevant repository test suite and `./scripts/doctor.sh`.

## Non-goals

- Do not change named-agent instructions, model pins, reasoning effort, or
  sandbox defaults.
- Do not add a legacy V1 profile.
- Do not change `agents.max_depth` or enable nested delegation.

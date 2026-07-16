# Enable Codebase Memory by Default

## Goal

Enable the `codebase_memory` MCP server in the portable base configuration so every device using this repository receives the default after bootstrap.

## Design

Change `mcp_servers.codebase_memory.enabled` from `false` to `true` in `.codex/config.toml`.

Preserve the existing profile behavior:

- `minimal` and `frontend` continue to disable Codebase Memory explicitly.
- `security` and `full` continue to enable it.

This keeps Codebase Memory available by default while retaining lightweight opt-out profiles.

## Verification

Regenerate the active configuration with `scripts/bootstrap.sh --apply`, confirm the generated base enables Codebase Memory, and run the repository validator and test suite. No unrelated configuration or MCP settings will change.

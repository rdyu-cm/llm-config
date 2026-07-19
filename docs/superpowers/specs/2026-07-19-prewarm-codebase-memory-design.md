# Prewarm Codebase Memory During Bootstrap

## Goal

Make a fresh portable Codex installation download and validate the pinned
`codebase-memory-mcp@0.8.1` package before Codex starts, so first-session MCP
availability does not depend on an implicit `npx` download during MCP startup.

## Design

On `scripts/bootstrap.sh --apply`, launch the pinned package once with standard
input redirected from `/dev/null`. The MCP server can initialize, populate the
npm execution cache, and exit on end-of-file. A failed launch fails bootstrap
visibly. Dry runs do not access npm or the network.

Update `scripts/doctor.sh` to launch the same pinned package with closed input
instead of checking for a global `codebase-memory-mcp` executable. The package
is intentionally managed through `npx`, so a global binary is not expected.

Increase `mcp_servers.codebase_memory.startup_timeout_sec` from 30 to 60 seconds
as a secondary allowance for slow startup. This timeout does not repair corrupt
npm state; bootstrap prewarming is the primary protection.

## Failure Behavior

- Missing Node.js or `npx` remains a required doctor failure.
- A failed package download or launch makes apply-mode bootstrap fail with the
  underlying npm error instead of leaving Codex to discover it later.
- Dry-run bootstrap remains non-mutating and does not download packages.

## Testing

- Bootstrap tests use a fake `npx` executable and assert apply mode invokes the
  pinned package with closed standard input.
- Bootstrap tests assert dry-run mode does not invoke `npx`.
- Configuration tests assert the startup timeout is 60 seconds.
- Existing repository validation and unit tests must remain green.

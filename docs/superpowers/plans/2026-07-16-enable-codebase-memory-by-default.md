# Enable Codebase Memory by Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the pinned Codebase Memory MCP server in the portable base configuration while preserving `minimal` and `frontend` as explicit opt-out profiles.

**Architecture:** The repository's `.codex/config.toml` remains the portable source of truth and bootstrap regenerates the active user config from it. A focused configuration test locks the base and profile enablement matrix, while the README documents the resulting defaults.

**Tech Stack:** TOML, Python `unittest`, Bash bootstrap scripts, Codex CLI

## Global Constraints

- Keep `codebase-memory-mcp` pinned at version `0.8.1`.
- Keep `minimal` and `frontend` configured with `codebase_memory.enabled = false`.
- Keep `security` and `full` configured with `codebase_memory.enabled = true`.
- Do not change any other MCP server setting.

---

### Task 1: Enable and verify the portable default

**Files:**
- Modify: `tests/test_capability_bundle.py`
- Modify: `.codex/config.toml:32-40`
- Modify: `README.md:82-106`
- Regenerate (ignored): `.codex/config.generated.toml`

**Interfaces:**
- Consumes: TOML configuration tables under `mcp_servers.codebase_memory`.
- Produces: A portable base with Codebase Memory enabled and a tested profile enablement matrix.

- [ ] **Step 1: Write the failing configuration test**

Add this method to `CapabilityBundleTests` in `tests/test_capability_bundle.py`:

```python
    def test_codebase_memory_is_enabled_by_default_with_explicit_opt_out_profiles(self):
        with (ROOT / ".codex/config.toml").open("rb") as handle:
            base = tomllib.load(handle)

        self.assertTrue(base["mcp_servers"]["codebase_memory"]["enabled"])

        expected = {
            "minimal": False,
            "frontend": False,
            "security": True,
            "full": True,
        }
        for profile, enabled in expected.items():
            with (ROOT / "profiles" / f"{profile}.config.toml").open("rb") as handle:
                config = tomllib.load(handle)
            self.assertEqual(config["mcp_servers"]["codebase_memory"]["enabled"], enabled)
```

- [ ] **Step 2: Run the focused test and verify that it fails**

Run:

```bash
python3 -m unittest tests.test_capability_bundle.CapabilityBundleTests.test_codebase_memory_is_enabled_by_default_with_explicit_opt_out_profiles -v
```

Expected: `FAIL` because `.codex/config.toml` currently has `codebase_memory.enabled = false`.

- [ ] **Step 3: Enable Codebase Memory in the portable base**

Change only the comment and enablement field in `.codex/config.toml`:

```toml
# Enabled by default; minimal and frontend profiles provide explicit opt-outs.
[mcp_servers.codebase_memory]
command = "npx"
args = ["-y", "codebase-memory-mcp@0.8.1"]
enabled = true
required = false
startup_timeout_sec = 30
tool_timeout_sec = 90
default_tools_approval_mode = "auto"
```

- [ ] **Step 4: Update the README to match the new behavior**

Replace the `codebase_memory` base-configuration bullet with:

```markdown
- `codebase_memory`: pinned to `codebase-memory-mcp@0.8.1` and enabled by default through `npx`. Minimal and frontend profiles disable it explicitly.
```

Keep the existing profile descriptions because they remain accurate.

- [ ] **Step 5: Regenerate the active configuration**

Run:

```bash
./scripts/bootstrap.sh --apply
```

Expected: bootstrap reports the merged config and existing discovery links as current or linked without conflicts.

- [ ] **Step 6: Verify the focused test and effective base setting**

Run:

```bash
python3 -m unittest tests.test_capability_bundle.CapabilityBundleTests.test_codebase_memory_is_enabled_by_default_with_explicit_opt_out_profiles -v
codex mcp get codebase_memory
```

Expected: the test reports `OK`; Codex reports `codebase_memory (enabled)`.

- [ ] **Step 7: Run repository verification**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: validation succeeds, all tests pass, and `git diff --check` produces no output.

- [ ] **Step 8: Commit the implementation**

```bash
git add .codex/config.toml README.md tests/test_capability_bundle.py
git commit -m "feat: enable codebase memory by default"
```

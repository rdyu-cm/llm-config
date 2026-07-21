# Enable Multi-Agent V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Multi-Agent V2 by default while preserving four concurrent child-agent slots and eliminating the incompatible legacy thread cap.

**Architecture:** The portable base config owns the V2 feature and its session-wide concurrency limit. A static TOML regression test locks the required relationship—five total V2 threads, no legacy `agents.max_threads`—while bootstrap regenerates the globally linked merged config.

**Tech Stack:** TOML, Python `unittest`, Bash bootstrap scripts, Codex CLI 0.144.6.

## Global Constraints

- Keep `agents.max_depth = 1` and every named agent registration unchanged.
- Preserve all Terra/Sol model pins, reasoning effort, and sandbox defaults.
- Configure five V2 session threads: one root plus four children.
- Expose spawn metadata so configured custom roles remain selectable.
- Register V2 tools under `agents`, not the model-reserved `collaboration` namespace.
- Do not add a legacy V1 profile.

---

### Task 1: Replace the legacy concurrency setting with V2 configuration

**Files:**
- Modify: `tests/test_capability_bundle.py`
- Modify: `.codex/config.toml`
- Regenerate: `.codex/config.generated.toml`

**Interfaces:**
- Consumes: Codex `features.multi_agent_v2` structured configuration and the existing bootstrap merge flow.
- Produces: A portable configuration where `multi_agent_v2.enabled` is `true`, `hide_spawn_agent_metadata` is `false`, `max_concurrent_threads_per_session` is `5`, `tool_namespace` is `"agents"`, and `agents.max_threads` is absent.

- [ ] **Step 1: Write the failing configuration regression test**

Add this method to `CapabilityBundleTests` in `tests/test_capability_bundle.py`:

```python
def test_multi_agent_v2_owns_concurrency_limit(self):
    with (ROOT / ".codex/config.toml").open("rb") as handle:
        base = tomllib.load(handle)

    self.assertEqual(
        base["features"]["multi_agent_v2"],
        {
            "enabled": True,
            "hide_spawn_agent_metadata": False,
            "max_concurrent_threads_per_session": 5,
            "tool_namespace": "agents",
        },
    )
    self.assertNotIn("max_threads", base["agents"])
    self.assertEqual(base["agents"]["max_depth"], 1)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python3 -m unittest tests.test_capability_bundle.CapabilityBundleTests.test_multi_agent_v2_owns_concurrency_limit -v
```

Expected: `ERROR` or `FAIL` because the config has no structured `multi_agent_v2` entry and still contains `agents.max_threads`.

- [ ] **Step 3: Apply the minimal portable configuration change**

Change the opening configuration block in `.codex/config.toml` to:

```toml
[features]
hooks = true

[features.multi_agent_v2]
enabled = true
hide_spawn_agent_metadata = false
max_concurrent_threads_per_session = 5
tool_namespace = "agents"

[agents]
max_depth = 1
```

Do not modify the named agent registrations below that block.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```bash
python3 -m unittest tests.test_capability_bundle.CapabilityBundleTests.test_multi_agent_v2_owns_concurrency_limit -v
```

Expected: one test passes.

- [ ] **Step 5: Regenerate the installed merged configuration**

Run:

```bash
./scripts/bootstrap.sh --apply
```

Expected: bootstrap regenerates `.codex/config.generated.toml`, keeps `~/.codex/config.toml` linked to it, and finishes successfully.

- [ ] **Step 6: Verify a real model request uses the non-reserved tool namespace**

Run:

```bash
timeout 30 codex exec --ephemeral -C /tmp 'Reply exactly OK.'
```

Expected: exits `0`, prints `OK`, and does not contain the reserved `collaboration.spawn_agent` schema error, `agents.max_threads cannot be set`, or a `thread/start failed` error.

- [ ] **Step 7: Run repository verification**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
./scripts/doctor.sh
git diff --check
```

Expected: all unit tests pass, doctor reports no required problems, and `git diff --check` exits successfully.

- [ ] **Step 8: Commit the implementation**

```bash
git add .codex/config.toml tests/test_capability_bundle.py
git commit -m "config: enable multi-agent v2 by default"
```

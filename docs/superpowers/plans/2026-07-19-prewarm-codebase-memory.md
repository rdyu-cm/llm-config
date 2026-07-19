# Prewarm Codebase Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download and validate the pinned Codebase Memory MCP package during portable-config bootstrap so the first Codex session does not perform an implicit package installation.

**Architecture:** Keep `npx` as the portable package runner, but invoke the exact pinned package during apply-mode bootstrap with stdin closed. Exercise the same launch in the doctor, and retain Codex's MCP timeout only as a secondary slow-start safeguard.

**Tech Stack:** POSIX shell, Python `unittest`, TOML, npm/npx

## Global Constraints

- Keep Codebase Memory pinned to `codebase-memory-mcp@0.8.1`.
- Apply-mode bootstrap must fail visibly if the package cannot download or launch.
- Dry-run bootstrap must not invoke npm or access the network.
- The doctor must not require a globally installed `codebase-memory-mcp` binary.
- Set `mcp_servers.codebase_memory.startup_timeout_sec` to exactly `60` seconds.

---

### Task 1: Prewarm and Validate the Pinned MCP Package

**Files:**
- Modify: `tests/test_bootstrap.py`
- Create: `tests/test_doctor.py`
- Modify: `tests/test_capability_bundle.py`
- Modify: `scripts/bootstrap.sh`
- Modify: `scripts/doctor.sh`
- Modify: `.codex/config.toml`

**Interfaces:**
- Consumes: `npx -y codebase-memory-mcp@0.8.1` from the existing MCP configuration.
- Produces: apply-only bootstrap prewarming, doctor launch validation, and a 60-second Codex MCP startup timeout.

- [ ] **Step 1: Write failing bootstrap tests**

Add a fake `npx` executable to the existing clean-home apply test. It records its arguments and fails if stdin is not closed:

```python
fake_bin = Path(directory) / "bin"
fake_bin.mkdir()
npx_log = Path(directory) / "npx.log"
fake_npx = fake_bin / "npx"
fake_npx.write_text(
    "#!/usr/bin/env bash\n"
    'printf "%s\\n" "$*" >> "$NPX_LOG"\n'
    "if IFS= read -r _; then exit 97; fi\n",
    encoding="utf-8",
)
fake_npx.chmod(0o755)
```

Pass the fake executable to the apply invocation:

```python
env={
    **os.environ,
    "HOME": str(home),
    "PYTHON": sys.executable,
    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
    "NPX_LOG": str(npx_log),
},
```

Then assert the pinned launch occurred:

```python
self.assertEqual(
    npx_log.read_text(encoding="utf-8"),
    "-y codebase-memory-mcp@0.8.1\n",
)
```

Add a separate dry-run test using the same fake executable and a fresh temporary `HOME`, then assert `npx_log` was not created:

```python
def test_dry_run_does_not_prewarm_codebase_memory(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory) / "home"
        fake_bin = Path(directory) / "bin"
        home.mkdir()
        fake_bin.mkdir()
        npx_log = Path(directory) / "npx.log"
        fake_npx = fake_bin / "npx"
        fake_npx.write_text(
            "#!/usr/bin/env bash\n"
            'printf "%s\\n" "$*" >> "$NPX_LOG"\n',
            encoding="utf-8",
        )
        fake_npx.chmod(0o755)

        result = subprocess.run(
            ["bash", str(ROOT / "scripts" / "bootstrap.sh"), "--dry-run"],
            env={
                **os.environ,
                "HOME": str(home),
                "PYTHON": sys.executable,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "NPX_LOG": str(npx_log),
            },
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(npx_log.exists())
```

- [ ] **Step 2: Write a failing doctor test**

Create `tests/test_doctor.py` with a temporary command directory. Stub required commands, make the Python stub return success for validation subprocesses, and make `npx` record its arguments while rejecting open stdin:

```python
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DoctorTests(unittest.TestCase):
    def test_launches_pinned_codebase_memory_package_with_closed_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory) / "bin"
            fake_bin.mkdir()
            npx_log = Path(directory) / "npx.log"

            for command in ("codex", "node", "python3"):
                path = fake_bin / command
                path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)

            npx = fake_bin / "npx"
            npx.write_text(
                "#!/usr/bin/env bash\n"
                'printf "%s\\n" "$*" >> "$NPX_LOG"\n'
                "if IFS= read -r _; then exit 97; fi\n",
                encoding="utf-8",
            )
            npx.chmod(0o755)

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "doctor.sh")],
                env={
                    **os.environ,
                    "PATH": str(fake_bin),
                    "PYTHON": str(fake_bin / "python3"),
                    "NPX_LOG": str(npx_log),
                },
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                npx_log.read_text(encoding="utf-8"),
                "-y codebase-memory-mcp@0.8.1\n",
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Write a failing timeout assertion**

Extend `test_codebase_memory_is_enabled_by_default_with_explicit_opt_out_profiles` after loading the base config:

```python
self.assertEqual(
    base["mcp_servers"]["codebase_memory"]["startup_timeout_sec"],
    60,
)
```

- [ ] **Step 4: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_bootstrap.BootstrapTests.test_apply_creates_codex_directory_in_clean_home \
  tests.test_bootstrap.BootstrapTests.test_dry_run_does_not_prewarm_codebase_memory \
  tests.test_doctor.DoctorTests.test_launches_pinned_codebase_memory_package_with_closed_stdin \
  tests.test_capability_bundle.CapabilityBundleTests.test_codebase_memory_is_enabled_by_default_with_explicit_opt_out_profiles \
  -v
```

Expected: FAIL because bootstrap does not invoke `npx`, doctor only checks for a global binary, and the timeout is 30.

- [ ] **Step 5: Implement apply-only bootstrap prewarming**

Add this function after `install_config` in `scripts/bootstrap.sh`:

```bash
prewarm_codebase_memory() {
  if [ "$APPLY" = false ]; then
    return
  fi
  echo "prewarm Codebase Memory"
  npx -y codebase-memory-mcp@0.8.1 </dev/null
}
```

Invoke it immediately after the successful `install_config` block:

```bash
if ! prewarm_codebase_memory; then
  echo "Codebase Memory prewarm failed; no discovery links were changed." >&2
  exit 1
fi
```

- [ ] **Step 6: Replace the doctor’s ineffective global-binary check**

Replace:

```bash
check_command "Codebase Memory binary" codebase-memory-mcp false
```

with:

```bash
if npx -y codebase-memory-mcp@0.8.1 </dev/null; then
  echo "ok      Codebase Memory MCP"
else
  echo "broken  Codebase Memory MCP" >&2
  failures=$((failures + 1))
fi
```

- [ ] **Step 7: Increase the MCP startup timeout**

In `.codex/config.toml`, change only:

```toml
startup_timeout_sec = 60
```

- [ ] **Step 8: Run focused tests and verify GREEN**

Run the command from Step 4.

Expected: all four tests report `ok` and the suite reports `OK`.

- [ ] **Step 9: Run repository verification**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Expected: validation succeeds, every test passes, and `git diff --check` emits no output.

- [ ] **Step 10: Regenerate and smoke-test the active configuration**

Run:

```bash
./scripts/bootstrap.sh --apply
codex mcp get codebase_memory
```

Expected: bootstrap prints `prewarm Codebase Memory`; Codex reports `codebase_memory` enabled with `startup_timeout_sec: 60`.

- [ ] **Step 11: Commit the implementation**

```bash
git add \
  .codex/config.toml \
  scripts/bootstrap.sh \
  scripts/doctor.sh \
  tests/test_bootstrap.py \
  tests/test_doctor.py \
  tests/test_capability_bundle.py \
  docs/superpowers/plans/2026-07-19-prewarm-codebase-memory.md
git commit -m "fix: prewarm codebase memory during bootstrap"
```

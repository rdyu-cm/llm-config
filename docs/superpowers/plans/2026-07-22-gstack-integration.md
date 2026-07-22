# Gstack Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pinned, single-repository gstack integration with browser-free workflow and complete local-VM installation modes, model-aware Codex subagent routing, explicit updates, and throttled startup notices.

**Architecture:** Keep a pristine upstream snapshot in `vendor/gstack`, checked-in Codex-generated skills in `generated/gstack-codex`, and all personal policy outside the vendor tree. A stdlib-only Python installer owns gstack links and profile switching, while the existing shell bootstrap remains the public entry point. Separate stdlib-only update-check and update-preparation utilities preserve reproducibility and never update the trusted vendor tree implicitly.

**Tech Stack:** Bash, Python 3.11 standard library, TOML, unittest, Git, Bun 1.3.10, upstream gstack at commit `a3259400a366593e0c909dd9ac3e59752efd2488`.

## Global Constraints

- Preserve `vendor/gstack` as an unmodified snapshot of upstream commit `a3259400a366593e0c909dd9ac3e59752efd2488`; generated files and personal policy live outside it.
- Preserve gstack's MIT license and record provenance in `sources.lock.toml`.
- `--gstack=off` remains the default and preserves existing bootstrap behavior.
- `--gstack=workflow` must not install, expose, build, download, or launch Chromium or gstack browser capabilities.
- `--gstack=full` installs the complete Codex-supported gstack catalog and browser runtime.
- Bun is pinned to `1.3.10`; verify installer SHA-256 `bab8acfb046aac8c72407bdcce903957665d655d7acaa3e11c7c4616beae68dd` before execution.
- Never overwrite unrelated files or symlinks under the user's home directory.
- Never commit, push, publish, import cookies, pair remote agents, or apply upstream updates automatically.
- Keep the existing Terra/Sol model pins in `.codex/agents/*.toml` unchanged.
- Use TDD for every behavior change and preserve the existing dirty-worktree safety rules.

---

### Task 1: Vendor Provenance and Integrity Contract

**Files:**
- Create: `vendor/gstack/**` from upstream commit `a3259400a366593e0c909dd9ac3e59752efd2488`
- Create: `vendor/gstack-source.toml`
- Modify: `sources.lock.toml`
- Modify: `scripts/validate.py`
- Test: `tests/test_gstack_vendor.py`

**Interfaces:**
- Consumes: the approved upstream repository and commit.
- Produces: `sources.lock.toml` entry named `gstack`; `validate_gstack_vendor(root: Path, lock: dict) -> None` for repository validation.

- [ ] **Step 1: Write the failing vendor contract tests**

```python
# tests/test_gstack_vendor.py
import tomllib
import unittest
from pathlib import Path

from scripts.validate import validate_gstack_vendor


ROOT = Path(__file__).resolve().parents[1]
PIN = "a3259400a366593e0c909dd9ac3e59752efd2488"


class GstackVendorTests(unittest.TestCase):
    def test_lock_and_vendor_identify_exact_upstream_revision(self) -> None:
        with (ROOT / "sources.lock.toml").open("rb") as handle:
            lock = tomllib.load(handle)
        source = next(item for item in lock["sources"] if item["name"] == "gstack")
        with (ROOT / "vendor/gstack-source.toml").open("rb") as handle:
            metadata = tomllib.load(handle)

        self.assertEqual(source["repository"], "https://github.com/garrytan/gstack")
        self.assertEqual(source["commit"], PIN)
        self.assertEqual(source["license"], "MIT (vendor/gstack/LICENSE)")
        validate_gstack_vendor(ROOT, lock)
        self.assertEqual(metadata["commit"], PIN)

    def test_vendor_does_not_contain_nested_git_metadata(self) -> None:
        self.assertFalse((ROOT / "vendor" / "gstack" / ".git").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_gstack_vendor -v`

Expected: FAIL because `validate_gstack_vendor` and `vendor/gstack` do not exist.

- [ ] **Step 3: Import the exact upstream tree without Git metadata**

Run:

```bash
tmpdir=$(mktemp -d)
git clone --filter=blob:none --no-checkout https://github.com/garrytan/gstack.git "$tmpdir/gstack"
git -C "$tmpdir/gstack" fetch --depth 1 origin a3259400a366593e0c909dd9ac3e59752efd2488
mkdir -p vendor/gstack
git -C "$tmpdir/gstack" archive a3259400a366593e0c909dd9ac3e59752efd2488 | tar -x -C vendor/gstack
```

Verify before continuing:

```bash
test -f vendor/gstack/LICENSE
test ! -e vendor/gstack/.git
```

Create `vendor/gstack-source.toml` beside the pristine tree:

```toml
repository = "https://github.com/garrytan/gstack"
commit = "a3259400a366593e0c909dd9ac3e59752efd2488"
```

- [ ] **Step 4: Add provenance and offline integrity validation**

Append this exact lock entry:

```toml
[[sources]]
name = "gstack"
repository = "https://github.com/garrytan/gstack"
commit = "a3259400a366593e0c909dd9ac3e59752efd2488"
license = "MIT (vendor/gstack/LICENSE)"
items = ["vendored-source", "generated-codex-skills", "workflow", "browser-runtime"]
```

Add to `scripts/validate.py`:

```python
def validate_gstack_vendor(root: Path, lock: dict) -> None:
    source = next((item for item in lock.get("sources", []) if item.get("name") == "gstack"), None)
    if source is None:
        fail("sources.lock.toml is missing gstack")
    vendor = root / "vendor" / "gstack"
    required = ("LICENSE", "setup", "package.json", "hosts/codex.ts")
    for relative in required:
        if not (vendor / relative).is_file():
            fail(f"vendor/gstack is missing {relative}")
    if (vendor / ".git").exists():
        fail("vendor/gstack must not contain nested Git metadata")
    license_text = (vendor / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in license_text or "Copyright (c) 2026 Garry Tan" not in license_text:
        fail("vendor/gstack/LICENSE is not the expected upstream MIT license")
    metadata = load_toml(root / "vendor" / "gstack-source.toml")
    if metadata.get("repository") != source.get("repository"):
        fail("gstack repository metadata does not match sources.lock.toml")
    if metadata.get("commit") != source.get("commit"):
        fail("gstack commit metadata does not match sources.lock.toml")
```

In `main()`, retain the parsed lock and validate it:

```python
    sources = load_toml(ROOT / "sources.lock.toml")
    validate_gstack_vendor(ROOT, sources)
```

- [ ] **Step 5: Run focused validation**

Run: `python3 -m unittest tests.test_gstack_vendor -v && python3 scripts/validate.py`

Expected: both commands exit 0 and validation reports the existing skill/agent counts.

- [ ] **Step 6: Commit the vendor contract**

```bash
git add vendor/gstack vendor/gstack-source.toml sources.lock.toml scripts/validate.py tests/test_gstack_vendor.py
git commit -m "build: vendor pinned gstack source"
```

---

### Task 2: Generated Codex Skills and Local Routing Policy

**Files:**
- Create: `generated/gstack-codex/gstack-*/SKILL.md`
- Create: `generated/gstack-codex/gstack-*/agents/openai.yaml`
- Create: `gstack-capabilities.toml`
- Modify: `AGENTS.global.md`
- Modify: `scripts/validate.py`
- Test: `tests/test_gstack_catalog.py`

**Interfaces:**
- Consumes: `vendor/gstack`, Bun 1.3.10, and upstream `bun run gen:skill-docs --host codex`.
- Produces: `gstack-capabilities.toml`; generated directories named `gstack-*`; routing heading `## Gstack subagent routing`.

- [ ] **Step 1: Write failing catalog and routing tests**

```python
# tests/test_gstack_catalog.py
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER_SKILLS = {
    "gstack-benchmark", "gstack-browse", "gstack-canary", "gstack-design-consultation",
    "gstack-design-review", "gstack-design-shotgun", "gstack-devex-review", "gstack-diagram",
    "gstack-ios-clean", "gstack-ios-design-review", "gstack-ios-fix", "gstack-ios-qa",
    "gstack-ios-sync", "gstack-land-and-deploy", "gstack-make-pdf", "gstack-open-gstack-browser",
    "gstack-pair-agent", "gstack-qa", "gstack-qa-only", "gstack-scrape",
    "gstack-setup-browser-cookies", "gstack-skillify",
}


class GstackCatalogTests(unittest.TestCase):
    def test_workflow_catalog_excludes_browser_capabilities(self) -> None:
        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        workflow = set(catalog["profiles"]["workflow"]["skills"])
        self.assertTrue({"gstack-office-hours", "gstack-plan-eng-review", "gstack-review", "gstack-ship"} <= workflow)
        self.assertFalse(workflow & BROWSER_SKILLS)
        self.assertNotIn("gstack-upgrade", workflow)

    def test_every_catalog_skill_has_generated_codex_frontmatter(self) -> None:
        with (ROOT / "gstack-capabilities.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        for name in catalog["profiles"]["full"]["skills"]:
            text = (ROOT / "generated" / "gstack-codex" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"name: {name}", text)
            self.assertIn("description:", text)

    def test_global_policy_preserves_model_aware_roles(self) -> None:
        policy = (ROOT / "AGENTS.global.md").read_text(encoding="utf-8")
        self.assertIn("## Gstack subagent routing", policy)
        self.assertIn("implementer_standard", policy)
        self.assertIn("security_reviewer", policy)
        self.assertIn("preserve the upstream subtask prompt verbatim", policy)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_gstack_catalog -v`

Expected: FAIL because the catalog and generated tree do not exist.

- [ ] **Step 3: Generate Codex artifacts at the pinned revision**

Install the pinned Bun only if needed, using the checksum from Global Constraints. Then run:

```bash
cd vendor/gstack
bun install --frozen-lockfile
bun run gen:skill-docs --host codex
cd ../..
mkdir -p generated/gstack-codex
cp -R vendor/gstack/.agents/skills/gstack-* generated/gstack-codex/
```

Do not copy the sidecar directory `vendor/gstack/.agents/skills/gstack`; runtime assets are installed separately in Task 3.

- [ ] **Step 4: Add the exact capability catalog**

Create `gstack-capabilities.toml` with `version = 1`, the Bun pin/checksum, and two lists. `profiles.workflow.skills` must contain:

```toml
skills = [
  "gstack-autoplan", "gstack-benchmark-models", "gstack-careful",
  "gstack-context-restore", "gstack-context-save", "gstack-cso",
  "gstack-document-generate", "gstack-document-release", "gstack-freeze",
  "gstack-guard", "gstack-health", "gstack-investigate", "gstack-landing-report",
  "gstack-learn", "gstack-office-hours", "gstack-plan-ceo-review",
  "gstack-plan-design-review", "gstack-plan-devex-review", "gstack-plan-eng-review",
  "gstack-plan-tune", "gstack-retro", "gstack-review", "gstack-setup-deploy",
  "gstack-setup-gbrain", "gstack-ship", "gstack-spec", "gstack-sync-gbrain",
  "gstack-unfreeze"
]
```

`profiles.full.skills` must list every generated `gstack-*` directory except `gstack-upgrade`; updates remain owned by `scripts/update-gstack.sh`. Sort both lists lexically so diffs are stable.

- [ ] **Step 5: Add the routing overlay**

Append this compact policy to `AGENTS.global.md`:

```markdown
## Gstack subagent routing

Keep vendored gstack prompts intact. When a gstack skill says to use the Agent tool with a general-purpose subagent, use Codex `spawn_agent`, preserve the upstream subtask prompt verbatim, and select the narrowest role: `explorer` for read-only discovery; `implementer_fast` or `implementer` for small writes; `implementer_standard` for multi-file integration; `implementer_deep` for broad design-sensitive implementation; `reviewer_standard` or `reviewer_deep` for correctness review; `security_reviewer` for security review; and `default` only when no narrow role fits. Do not set Terra as the unnamed global default. Existing agent files remain authoritative for model and reasoning effort.
```

- [ ] **Step 6: Validate generated inventory**

Extend `scripts/validate.py` to load `gstack-capabilities.toml`, reject duplicate/missing names, validate generated frontmatter with `parse_frontmatter`, and reject any workflow name absent from the full list.

Run: `python3 -m unittest tests.test_gstack_catalog -v && python3 scripts/validate.py`

Expected: all tests pass; validation reports the personal inventory and a separate gstack generated-skill count.

- [ ] **Step 7: Commit generated skills and routing**

```bash
git add generated/gstack-codex gstack-capabilities.toml AGENTS.global.md scripts/validate.py tests/test_gstack_catalog.py
git commit -m "feat: add generated gstack Codex catalog"
```

---

### Task 3: Idempotent Gstack Profile Installer

**Files:**
- Create: `scripts/install_gstack.py`
- Test: `tests/test_install_gstack.py`

**Interfaces:**
- Consumes: `gstack-capabilities.toml`, `generated/gstack-codex`, `vendor/gstack`, `HOME`, `--mode {off,workflow,full}`, and `--apply`.
- Produces: `install(root: Path, home: Path, mode: str, apply: bool) -> list[str]`; managed state at `~/.codex/gstack-managed.json`; skill links under `~/.codex/skills/`.

- [ ] **Step 1: Write failing installer tests**

```python
# tests/test_install_gstack.py
import json
import tempfile
import unittest
from pathlib import Path

from scripts.install_gstack import install


ROOT = Path(__file__).resolve().parents[1]


class InstallGstackTests(unittest.TestCase):
    def test_workflow_links_only_allowlisted_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            install(ROOT, home, "workflow", True)
            self.assertTrue((home / ".codex/skills/gstack-office-hours").is_symlink())
            self.assertFalse((home / ".codex/skills/gstack-browse").exists())
            state = json.loads((home / ".codex/gstack-managed.json").read_text())
            self.assertEqual(state["mode"], "workflow")

    def test_switching_full_to_workflow_removes_only_managed_browser_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            unrelated = home / ".codex/skills/user-skill"
            unrelated.mkdir(parents=True)
            install(ROOT, home, "full", True)
            self.assertTrue((home / ".codex/skills/gstack-browse").exists())
            install(ROOT, home, "workflow", True)
            self.assertFalse((home / ".codex/skills/gstack-browse").exists())
            self.assertTrue(unrelated.is_dir())

    def test_dry_run_and_conflicts_do_not_mutate_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            conflict = home / ".codex/skills/gstack-office-hours"
            conflict.mkdir(parents=True)
            messages = install(ROOT, home, "workflow", False)
            self.assertTrue(any("conflict" in line for line in messages))
            self.assertFalse((home / ".codex/gstack-managed.json").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_install_gstack -v`

Expected: FAIL because `scripts.install_gstack` does not exist.

- [ ] **Step 3: Implement catalog loading and desired-link calculation**

In `scripts/install_gstack.py`, define:

```python
STATE_RELATIVE = Path(".codex/gstack-managed.json")


def load_catalog(root: Path) -> dict:
    with (root / "gstack-capabilities.toml").open("rb") as handle:
        return tomllib.load(handle)


def desired_links(root: Path, home: Path, mode: str) -> dict[Path, Path]:
    if mode == "off":
        return {}
    catalog = load_catalog(root)
    skills = catalog["profiles"][mode]["skills"]
    links = {
        home / ".codex" / "skills" / name: root / "generated" / "gstack-codex" / name
        for name in skills
    }
    runtime = home / ".codex" / "skills" / "gstack"
    links[runtime / "bin"] = root / "vendor" / "gstack" / "bin"
    links[runtime / "ETHOS.md"] = root / "vendor" / "gstack" / "ETHOS.md"
    links[runtime / "review"] = root / "vendor" / "gstack" / "review"
    if mode == "full":
        links[runtime / "browse"] = root / "vendor" / "gstack" / "browse"
        links[runtime / "qa"] = root / "vendor" / "gstack" / "qa"
    return links
```

- [ ] **Step 4: Implement safe reconciliation and rollback**

`install()` must preflight every desired target, reject existing non-managed paths, and only then mutate. Store state as:

```json
{"version": 1, "mode": "workflow", "links": {"/absolute/target": "/absolute/source"}}
```

Delete an old link only when it is listed in state, is still a symlink, and resolves to the recorded source. On any creation failure, remove only links created during that invocation and restore the previous state file atomically. Use `Path.symlink_to(..., target_is_directory=source.is_dir())` and write state through `gstack-managed.json.tmp` followed by `Path.replace()`.

- [ ] **Step 5: Add CLI behavior**

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mode", choices=("off", "workflow", "full"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for message in install(args.root.resolve(), Path.home(), args.mode, args.apply):
        print(message)
    return 0
```

Catch `OSError`, `ValueError`, and `tomllib.TOMLDecodeError`, print `gstack install failed: ...` to stderr, and exit 1.

- [ ] **Step 6: Run installer tests**

Run: `python3 -m unittest tests.test_install_gstack -v`

Expected: all tests pass, including repeated installation and full-to-workflow cleanup.

- [ ] **Step 7: Commit the profile installer**

```bash
git add scripts/install_gstack.py tests/test_install_gstack.py
git commit -m "feat: add gstack profile installer"
```

---

### Task 4: Bootstrap Flags and Verified Dependencies

**Files:**
- Create: `scripts/prepare_gstack.py`
- Modify: `scripts/bootstrap.sh`
- Modify: `tests/test_bootstrap.py`
- Test: `tests/test_prepare_gstack.py`

**Interfaces:**
- Consumes: `--gstack=off|workflow|full`, `--apply`, catalog Bun pin/checksum, and `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD`.
- Produces: `prepare(root: Path, mode: str, apply: bool, env: dict[str, str]) -> list[str]`; installed Bun when required; built gstack runtime only for full mode.

- [ ] **Step 1: Write failing dependency tests**

```python
# tests/test_prepare_gstack.py
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_gstack import prepare


ROOT = Path(__file__).resolve().parents[1]


class PrepareGstackTests(unittest.TestCase):
    def test_off_does_not_require_bun(self) -> None:
        self.assertEqual(prepare(ROOT, "off", True, {"PATH": ""}), [])

    def test_workflow_sets_browser_download_skip(self) -> None:
        with patch("scripts.prepare_gstack.find_bun", return_value=Path("/fake/bun")), \
             patch("scripts.prepare_gstack.subprocess.run") as run:
            prepare(ROOT, "workflow", True, {"PATH": "/fake"})
        install_call = run.call_args_list[0]
        self.assertEqual(install_call.args[0][-3:], ["install", "--frozen-lockfile"])
        self.assertEqual(install_call.kwargs["env"]["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"], "1")
        self.assertFalse(any("build" in call.args[0] for call in run.call_args_list))

    def test_checksum_mismatch_stops_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             patch("scripts.prepare_gstack.find_bun", return_value=None), \
             patch("scripts.prepare_gstack.download_installer", return_value=Path(directory) / "bun-install"):
            installer = Path(directory) / "bun-install"
            installer.write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                prepare(ROOT, "workflow", True, {"PATH": ""})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Extend bootstrap tests before implementation**

Add table-driven cases to `tests/test_bootstrap.py` asserting:

```python
for mode in ("off", "workflow", "full"):
    result = subprocess.run(
        ["bash", str(fixture / "scripts/bootstrap.sh"), "--dry-run", f"--gstack={mode}"],
        env={**os.environ, "HOME": str(home), "PYTHON": sys.executable},
        capture_output=True,
        text=True,
    )
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertIn(f"gstack mode: {mode}", result.stdout)
```

Also assert invalid mode exits 2 and dry-run never invokes Bun, npx, curl, or the gstack installer in apply mode.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_prepare_gstack tests.test_bootstrap -v`

Expected: FAIL because the dependency module and CLI flag do not exist.

- [ ] **Step 4: Implement verified Bun preparation**

`scripts/prepare_gstack.py` must:

```python
def prepare(root: Path, mode: str, apply: bool, env: dict[str, str]) -> list[str]:
    if mode == "off":
        return []
    catalog = load_catalog(root)
    bun = find_bun(env)
    messages = []
    if bun is None:
        if not apply:
            return [f"would   install Bun {catalog['bun']['version']}"]
        installer = download_installer()
        verify_sha256(installer, catalog["bun"]["installer_sha256"])
        run_bun_installer(installer, catalog["bun"]["version"], env)
        bun = find_bun(env | {"PATH": f"{Path.home() / '.bun/bin'}{os.pathsep}{env.get('PATH', '')}"})
        if bun is None:
            raise RuntimeError("Bun installation completed but bun is unavailable")
    if not apply:
        return messages + [f"would   prepare gstack {mode}"]
    child_env = dict(env)
    if mode == "workflow":
        child_env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    subprocess.run([str(bun), "install", "--frozen-lockfile"], cwd=root / "vendor/gstack", env=child_env, check=True)
    if mode == "full":
        subprocess.run([str(bun), "run", "build"], cwd=root / "vendor/gstack", env=child_env, check=True)
    return messages + [f"ready   gstack {mode}"]
```

Use `urllib.request.urlopen("https://bun.sh/install", timeout=15)` into a `tempfile.NamedTemporaryFile(delete=False)`. Hash in 1 MiB chunks with `hashlib.sha256`. Execute only after the exact checksum matches.

- [ ] **Step 5: Parse bootstrap options without positional ordering constraints**

Replace the single-argument parser in `scripts/bootstrap.sh` with a loop accepting `--dry-run`, `--apply`, and `--gstack=MODE`, rejecting duplicates or unknown values. Default `GSTACK_MODE=off`.

Before `install_config`, call:

```bash
echo "gstack mode: $GSTACK_MODE"
"$PYTHON" "$ROOT/scripts/prepare_gstack.py" --root "$ROOT" --mode "$GSTACK_MODE" $([ "$APPLY" = true ] && echo --apply)
```

After existing discovery links succeed, call:

```bash
gstack_args="--root $ROOT --mode $GSTACK_MODE"
if [ "$APPLY" = true ]; then
  "$PYTHON" "$ROOT/scripts/install_gstack.py" --root "$ROOT" --mode "$GSTACK_MODE" --apply
else
  "$PYTHON" "$ROOT/scripts/install_gstack.py" --root "$ROOT" --mode "$GSTACK_MODE"
fi
```

Do not use command substitution in the final implementation; the first snippet describes placement only. Use an explicit `if` so paths remain correctly quoted.

- [ ] **Step 6: Run focused bootstrap tests**

Run: `python3 -m unittest tests.test_prepare_gstack tests.test_install_gstack tests.test_bootstrap -v`

Expected: all tests pass without real network or Bun execution.

- [ ] **Step 7: Commit bootstrap integration**

```bash
git add scripts/prepare_gstack.py scripts/bootstrap.sh tests/test_prepare_gstack.py tests/test_bootstrap.py
git commit -m "feat: add gstack bootstrap modes"
```

---

### Task 5: Throttled Startup Update Notification

**Files:**
- Create: `scripts/gstack_updates.py`
- Modify: `.codex/hooks/session_context.py`
- Modify: `scripts/bootstrap.sh`
- Modify: `tests/test_hooks.py`
- Test: `tests/test_gstack_updates.py`

**Interfaces:**
- Consumes: `sources.lock.toml`, upstream `HEAD`, cache age, `CODEX_CONFIG_UPDATE_CHECK`, and optional `GSTACK_REMOTE_HEAD` test seam.
- Produces: `check_update(lock_path: Path, cache_path: Path, force: bool, remote_head: str | None = None) -> str | None`; cache JSON under `$XDG_CACHE_HOME/codex-config/gstack-update.json` or `~/.cache/codex-config/gstack-update.json`.

- [ ] **Step 1: Write failing checker tests**

```python
# tests/test_gstack_updates.py
import json
import tempfile
import unittest
from pathlib import Path

from scripts.gstack_updates import check_update


ROOT = Path(__file__).resolve().parents[1]


class GstackUpdateTests(unittest.TestCase):
    def test_reports_changed_remote_head_and_caches_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            notice = check_update(
                ROOT / "sources.lock.toml", cache, True,
                remote_head="84be2f97c4190000000000000000000000000000",
            )
            self.assertIn("update  gstack:", notice)
            self.assertEqual(json.loads(cache.read_text())["head"][:12], "84be2f97c419")

    def test_fresh_cache_avoids_remote_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            cache.write_text(json.dumps({"checked_at": 4102444800, "head": "84be2f97c419"}))
            notice = check_update(ROOT / "sources.lock.toml", cache, False)
            self.assertIn("84be2f97c419", notice)

    def test_network_failure_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "update.json"
            self.assertIsNone(check_update(ROOT / "sources.lock.toml", cache, True, remote_head=""))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Add failing hook tests**

Update the `run_hook` helper to accept environment overrides. Add assertions that a supplied changed `GSTACK_REMOTE_HEAD` appears in `additionalContext`, while `CODEX_CONFIG_UPDATE_CHECK=0` omits it.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_gstack_updates tests.test_hooks -v`

Expected: FAIL because the checker does not exist and the hook has no update context.

- [ ] **Step 4: Implement the stdlib-only checker**

Use `git ls-remote <repository> HEAD` with `subprocess.run(..., timeout=2, check=True, capture_output=True, text=True)`. Accept only a 40-character lowercase hexadecimal head. Cache atomically with mode `0o600`, fields `version`, `checked_at`, `pinned`, and `head`. Treat malformed, missing, or expired cache as absent.

Format only changed heads:

```python
return (
    f"update  gstack: {pinned[:12]} -> {head[:12]}\n"
    "        run ./scripts/update-gstack.sh"
)
```

The CLI supports `--notify` and `--force`; it always exits 0 for network/cache errors and prints nothing.

- [ ] **Step 5: Integrate the session hook and bootstrap**

In `session_context.py`, add the repository `scripts` directory to `sys.path`, call `check_update` unless opted out, and append a returned notice to the existing context. Catch every `OSError`, `ValueError`, `subprocess.SubprocessError`, and TOML/JSON parse error so SessionStart output remains valid JSON.

At the end of bootstrap, call:

```bash
if [ "${CODEX_CONFIG_UPDATE_CHECK:-1}" != "0" ]; then
  "$PYTHON" "$ROOT/scripts/gstack_updates.py" --notify --force || true
fi
```

- [ ] **Step 6: Run update and hook tests**

Run: `python3 -m unittest tests.test_gstack_updates tests.test_hooks tests.test_bootstrap -v`

Expected: all tests pass; offline and opt-out cases produce valid hook JSON without notices.

- [ ] **Step 7: Commit startup notifications**

```bash
git add scripts/gstack_updates.py .codex/hooks/session_context.py scripts/bootstrap.sh tests/test_gstack_updates.py tests/test_hooks.py tests/test_bootstrap.py
git commit -m "feat: notify when gstack updates are available"
```

---

### Task 6: Explicit Gstack Update Preparation

**Files:**
- Create: `scripts/update_gstack.py`
- Create: `scripts/update-gstack.sh`
- Modify: `scripts/update.sh`
- Test: `tests/test_update_gstack.py`

**Interfaces:**
- Consumes: current gstack lock entry, candidate commit from `git ls-remote`, GitHub commit archive, Bun generator, and repository root.
- Produces: `prepare_update(root: Path, candidate: str, archive: Path) -> None`; uncommitted changes limited to `vendor/gstack`, `vendor/gstack-source.toml`, `generated/gstack-codex`, and `sources.lock.toml`.

- [ ] **Step 1: Write failing archive validation and replacement tests**

```python
# tests/test_update_gstack.py
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.update_gstack import extract_archive, validate_candidate


class UpdateGstackTests(unittest.TestCase):
    def test_rejects_non_commit_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "40 hexadecimal"):
            validate_candidate("main")

    def test_extract_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                info = tarfile.TarInfo("gstack-abc/../../escape")
                info.size = 1
                handle.addfile(info, io.BytesIO(b"x"))
            with self.assertRaisesRegex(ValueError, "unsafe archive path"):
                extract_archive(archive, Path(directory) / "out")


if __name__ == "__main__":
    unittest.main()
```

Add an integration test using a tiny valid archive with `LICENSE`, `setup`, `package.json`, and `hosts/codex.ts`. Mock skill generation and assert replacement is confined to the four allowed paths and remains uncommitted.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_update_gstack -v`

Expected: FAIL because `scripts.update_gstack` does not exist.

- [ ] **Step 3: Implement safe archive download and extraction**

Validate candidates with `re.fullmatch(r"[0-9a-f]{40}", candidate)`. Download `https://github.com/garrytan/gstack/archive/{candidate}.tar.gz` with a 30-second timeout. For every tar member, reject absolute paths, `..` components, devices, FIFOs, and links whose resolved target escapes the extraction root. Extract into `tempfile.TemporaryDirectory()` and validate required vendor files before touching the repository.

- [ ] **Step 4: Implement staged replacement and lock update**

Copy the candidate vendor tree and generated Codex output into temporary sibling directories. Run the pinned Bun generator against the staged vendor tree. Only after validation succeeds:

```python
replace_directory(staged_vendor, root / "vendor/gstack")
replace_directory(staged_generated, root / "generated/gstack-codex")
update_lock_commit(root / "sources.lock.toml", candidate)
write_source_metadata(root / "vendor/gstack-source.toml", candidate)
```

`replace_directory` renames the existing directory to a temporary backup, renames the staged directory into place, and restores the backup if the second rename fails. `update_lock_commit` changes only the `commit` line within the `[[sources]]` table whose name is `gstack`, preserving all other TOML text. `write_source_metadata` atomically writes the same repository URL and candidate commit beside the pristine vendor directory.

- [ ] **Step 5: Add shell entry point and retain general checker behavior**

```bash
#!/usr/bin/env bash
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$ROOT/scripts/update_gstack.py" --root "$ROOT" "$@"
```

Keep `scripts/update.sh` check-only. Its existing loop automatically includes the new gstack lock entry; update its rejection message to direct gstack users to `scripts/update-gstack.sh` while retaining manual instructions for other sources.

- [ ] **Step 6: Run focused updater checks**

Run: `python3 -m unittest tests.test_update_gstack tests.test_gstack_vendor tests.test_gstack_catalog -v`

Expected: all tests pass without contacting GitHub.

Run an explicit read-only check: `./scripts/update-gstack.sh --check`

Expected: prints pinned and upstream commits and makes no working-tree changes.

- [ ] **Step 7: Commit the update workflow**

```bash
git add scripts/update_gstack.py scripts/update-gstack.sh scripts/update.sh tests/test_update_gstack.py
git commit -m "feat: add reviewed gstack update workflow"
```

---

### Task 7: Documentation, Capability Catalog, and End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `capability-bundle.toml`
- Modify: `scripts/doctor.sh`
- Modify: `tests/test_capability_bundle.py`
- Modify: `tests/test_doctor.py`
- Modify: `tests/test_external_cwd.py`

**Interfaces:**
- Consumes: all prior task interfaces.
- Produces: documented commands; capability entries for gstack source/catalog; doctor checks for selected installed mode.

- [ ] **Step 1: Write failing catalog and doctor assertions**

In `tests/test_capability_bundle.py`, assert:

```python
components = {item["name"]: item for item in bundle["components"]}
self.assertEqual(components["gstack-source"]["path"], "vendor/gstack")
self.assertEqual(components["gstack-codex-skills"]["path"], "generated/gstack-codex")
```

In `tests/test_doctor.py`, create temporary workflow state and assert doctor reports `ok      gstack workflow`; create a managed link to the wrong source and assert doctor exits nonzero with `gstack managed link mismatch`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_capability_bundle tests.test_doctor -v`

Expected: FAIL because the bundle and doctor do not know about gstack.

- [ ] **Step 3: Document exact installation and update commands**

Add README sections covering:

```markdown
## Gstack workflow

Gstack is vendored at the commit recorded in `sources.lock.toml`. Personal skills and model-pinned agents remain separate from the pristine upstream snapshot.

```bash
# Existing portable config only
./scripts/bootstrap.sh --apply --gstack=off

# Cluster: planning, review, debugging, security, docs, and shipping; no browser
./scripts/bootstrap.sh --apply --gstack=workflow

# Local VM: complete gstack including Chromium-backed browser and QA
./scripts/bootstrap.sh --apply --gstack=full
```

Startup checks for a newer upstream commit at most once every 24 hours. Set `CODEX_CONFIG_UPDATE_CHECK=0` to disable that notice. Run `./scripts/update-gstack.sh --check` to check immediately and `./scripts/update-gstack.sh` to prepare an uncommitted vendor update for review.
```

Also document that Bun is installed from a pinned, checksum-verified installer when needed, Chromium is full-mode only, and cookie import/pairing remain explicit commands.

- [ ] **Step 4: Register gstack components**

Append to `capability-bundle.toml`:

```toml
[[components]]
name = "gstack-source"
kind = "vendor"
path = "vendor/gstack"
classification = "supported"

[[components]]
name = "gstack-codex-skills"
kind = "generated-skills"
path = "generated/gstack-codex"
classification = "supported"
```

- [ ] **Step 5: Extend doctor checks**

If `~/.codex/gstack-managed.json` is absent, report no gstack status and preserve the existing exit behavior. If present, validate JSON version/mode and every recorded link against its source. Report `ok      gstack workflow` or `ok      gstack full`; report mismatches on stderr and mark doctor failed. Do not contact the network or start the browser from doctor.

- [ ] **Step 6: Run the complete repository suite**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
git diff --check
```

Expected: all unittest cases pass, repository validation exits 0, and `git diff --check` emits no output.

- [ ] **Step 7: Run isolated bootstrap smoke checks**

Run workflow mode with a temporary `HOME` and mocked/preinstalled Bun. Verify `gstack-office-hours` is linked, `gstack-browse` is absent, and `~/.codex/skills/gstack/browse` is absent.

On a machine with browser dependencies, run full mode and then invoke the vendored browser health command. Verify `gstack-browse` is linked and the daemon binds only to loopback. If browser dependencies are unavailable, record the full-mode smoke as skipped while keeping all mocked integration tests passing.

- [ ] **Step 8: Commit documentation and final integration checks**

```bash
git add README.md capability-bundle.toml scripts/doctor.sh tests/test_capability_bundle.py tests/test_doctor.py tests/test_external_cwd.py
git commit -m "docs: document portable gstack profiles"
```

- [ ] **Step 9: Final branch verification**

Run:

```bash
./scripts/doctor.sh
python3 -m unittest discover -s tests -v
git diff --check
git status --short
```

Expected: doctor reports repository configuration and any installed gstack mode accurately; all tests pass; whitespace check is empty; working tree is clean.

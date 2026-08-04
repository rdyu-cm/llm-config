# Lightweight ECC Scientific Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five lightweight, provider-neutral scientific research skills derived from a pinned ECC revision and a read-only helper for reviewing relevant upstream changes.

**Architecture:** The existing shared `skills/` directory remains the only discovery surface for both providers. ECC is recorded as an audited design source at commit `7a5757e6c0d7e8e1080d30169b4b044d76e0f7fc`; a standalone Python helper compares that pin with a candidate revision in a temporary Git repository and never updates local files.

**Tech Stack:** Markdown skills, TOML catalogs, Python 3.11 standard library, POSIX shell, `unittest`, Git.

## Global Constraints

- Install no ECC plugin, global instructions, agents, commands, hooks, rules, dashboard, runtime, or MCP server.
- Keep one shared copy of each skill for Claude Code and Codex.
- All upstream updates are review-only and require manual application and pin changes.
- Add no scientific-writing skill, automatic memory recall, continuous learning, or parallel research agent.
- Preserve the existing no-argument `scripts/update.sh` behavior and rejection of `--apply`.

---

### Task 1: Lock and catalog the scientific skill set

**Files:**
- Modify: `tests/test_portable.py`
- Modify: `sources.lock.toml`
- Modify: `capability-bundle.toml`

**Interfaces:**
- Consumes: existing TOML source and component schemas.
- Produces: an `ecc` source entry and five `kind = "skill"` components used by validation and installation.

- [ ] **Step 1: Write the failing governance test**

Add a test that loads both TOML files and asserts the ECC repository, exact 40-character commit, MIT license, exact five upstream items, exact five local component names and paths, and absence of ECC runtime component kinds.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_portable.SharedSkillTests.test_scientific_ecc_sources_are_narrow_and_pinned -v`

Expected: failure because no ECC source or scientific components exist.

- [ ] **Step 3: Add the minimal lock and catalog entries**

Append one `[[sources]]` entry containing the official repository, pinned commit, MIT license, upstream source items, and local adaptation names. Add five supported skill components pointing to `skills/scientific-research`, `skills/research-eval`, `skills/research-memory`, `skills/research-compact`, and `skills/scientific-ml`.

- [ ] **Step 4: Run the focused governance test**

Run the command from Step 2. Expected: failure only because the five skill paths do not exist yet, proving the catalog is now visible.

- [ ] **Step 5: Commit the governance metadata with Task 2**

Do not create a broken intermediate commit; the paths become valid in Task 2.

### Task 2: Add the five adapted scientific skills

**Files:**
- Create: `skills/scientific-research/SKILL.md`
- Create: `skills/research-eval/SKILL.md`
- Create: `skills/research-memory/SKILL.md`
- Create: `skills/research-compact/SKILL.md`
- Create: `skills/scientific-ml/SKILL.md`
- Modify: `tests/test_portable.py`

**Interfaces:**
- Consumes: the approved design and catalog paths from Task 1.
- Produces: five direct-child skills with matching YAML `name` fields and provider-neutral workflows.

- [ ] **Step 1: Extend the failing test with semantic gates**

Assert that every skill identifies the pinned ECC design source and local adaptation, and add focused checks for durable cited artifacts, explicit evaluation verdicts, unreviewed memory trust, reference-not-duplicate compaction with redaction, and ML experiment question/verdict plus reproducibility controls.

- [ ] **Step 2: Run the focused test to verify it fails**

Run the Task 1 test. Expected: failure on missing `SKILL.md` files.

- [ ] **Step 3: Write the minimal skill files**

Implement concise workflows with checkable completion criteria. Keep common research rules in `scientific-research`; other skills reference it instead of duplicating source-quality guidance. Use progressive disclosure only if a branch-specific reference becomes necessary; no extra reference file is required initially.

- [ ] **Step 4: Run the focused test and validator**

Run:

```bash
python3 -m unittest tests.test_portable.SharedSkillTests.test_scientific_ecc_sources_are_narrow_and_pinned -v
python3 scripts/validate.py
```

Expected: both pass and the validator reports 32 skills.

- [ ] **Step 5: Commit Tasks 1 and 2**

```bash
git add sources.lock.toml capability-bundle.toml skills/scientific-research skills/research-eval skills/research-memory skills/research-compact skills/scientific-ml tests/test_portable.py
git commit -m "feat: add lightweight scientific research skills"
```

### Task 3: Add the read-only ECC update-review helper

**Files:**
- Create: `scripts/review_ecc_updates.py`
- Modify: `scripts/update.sh`
- Modify: `tests/test_portable.py`

**Interfaces:**
- Consumes: `sources.lock.toml`, its `ecc` source, optional `--candidate REV`, and Git.
- Produces: stdout containing pinned/candidate revisions and filtered name-status changes; returns 0 for a completed review and nonzero for invalid input or Git/network failure.

- [ ] **Step 1: Write failing local-repository tests**

Create a temporary Git repository with a pinned commit, one adopted-path change, and one unrelated change. Write a temporary lock pointing to that repository. Assert that the helper reports only `skills/deep-research/...`, leaves the repository and lock byte-identical, and rejects a lock without ECC. Add a shell-dispatch assertion for `scripts/update.sh --review ecc --lock ... --candidate ...`.

- [ ] **Step 2: Run the helper tests to verify they fail**

Run: `python3 -m unittest tests.test_portable.EccUpdateReviewTests -v`

Expected: failure because `scripts/review_ecc_updates.py` and the update mode do not exist.

- [ ] **Step 3: Implement the minimal helper**

Use `argparse`, `tomllib`, `tempfile.TemporaryDirectory`, and `subprocess.run`. Resolve HEAD with `git ls-remote` only when `--candidate` is absent. Initialize a temporary repository, fetch the pinned and candidate revisions, and run `git diff --name-status --find-renames` restricted to the five upstream directories. Print manual review instructions and never write outside the temporary directory.

- [ ] **Step 4: Add shell dispatch without changing existing modes**

Recognize `--review ecc`, shift those two arguments, and `exec python3 "$ROOT/scripts/review_ecc_updates.py" "$@"`. Preserve no-argument behavior, `--apply` rejection, and invalid-argument usage failure.

- [ ] **Step 5: Run focused and regression tests**

Run:

```bash
python3 -m unittest tests.test_portable.EccUpdateReviewTests -v
python3 -m unittest discover -s tests -v
bash -n scripts/update.sh
```

Expected: all tests pass and shell syntax exits zero.

- [ ] **Step 6: Commit**

```bash
git add scripts/review_ecc_updates.py scripts/update.sh tests/test_portable.py
git commit -m "feat: review pinned ECC source updates"
```

### Task 4: Document and verify the completed integration

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the installed skill names and update helper CLI.
- Produces: user-facing scientific-research and update-review documentation.

- [ ] **Step 1: Add a failing documentation assertion**

Extend the governance test to require all five names, `scripts/update.sh --review ecc`, and explicit wording that updates are never automatically applied.

- [ ] **Step 2: Run the assertion to verify it fails**

Run the focused governance test. Expected: failure because README lacks the section.

- [ ] **Step 3: Add the concise README section**

Describe the five skills, their selective ECC provenance, the absence of ECC runtime installation, and the review-only update command.

- [ ] **Step 4: Run full verification**

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap.sh scripts/doctor.sh scripts/update.sh
./scripts/bootstrap.sh --dry-run
git diff --check
```

Expected: validator reports 32 skills, all tests pass, scripts parse, dry run remains non-mutating, and diff check is clean.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_portable.py
git commit -m "docs: describe scientific research skills"
```

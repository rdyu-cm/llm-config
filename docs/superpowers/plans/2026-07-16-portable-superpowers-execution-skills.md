# Portable Superpowers Execution Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor the pinned Superpowers execution workflow skills into `codex-config` so they are Git-portable and discovered after bootstrap on another machine.

**Architecture:** Install three complete standalone skill directories from the Superpowers commit already pinned in `sources.lock.toml`. Keep the full plugin disabled, record the expanded audited inventory, and verify both skill payload completeness and bootstrap discovery through the repository's stdlib-only tests and doctor.

**Tech Stack:** Codex skills, Python `unittest`, Bash, TOML, Git

## Global Constraints

- Source every skill from Superpowers commit `d884ae04edebef577e82ff7c4e143debd0bbec99`.
- Vendor only `executing-plans`, `subagent-driven-development`, and `using-git-worktrees`.
- Preserve every file in each selected upstream skill directory.
- Keep `superpowers@openai-curated` disabled and do not commit Codex caches or machine state.
- Preserve the existing `~/.agents/skills -> <clone>/skills` bootstrap architecture.

---

### Task 1: Vendor and register the execution skills

**Files:**
- Create: `skills/executing-plans/` from the pinned upstream directory
- Create: `skills/subagent-driven-development/` from the pinned upstream directory
- Create: `skills/using-git-worktrees/` from the pinned upstream directory
- Modify: `tests/test_bootstrap.py`
- Modify: `sources.lock.toml`
- Modify: `plugins.lock.toml`
- Modify: `README.md`

**Interfaces:**
- Consumes: the existing Superpowers source pin and the bootstrap's canonical `skills/` directory.
- Produces: three validated, complete standalone skill payloads discoverable through `~/.agents/skills` after bootstrap.

- [ ] **Step 1: Add a failing portable skill inventory test**

Add this test class to `tests/test_bootstrap.py`:

```python
class PortableSkillInventoryTests(unittest.TestCase):
    def test_execution_skills_include_required_payloads(self) -> None:
        expected = {
            "executing-plans": {"SKILL.md"},
            "subagent-driven-development": {
                "SKILL.md",
                "implementer-prompt.md",
                "spec-reviewer-prompt.md",
                "code-quality-reviewer-prompt.md",
            },
            "using-git-worktrees": {"SKILL.md"},
        }

        for skill_name, relative_paths in expected.items():
            for relative_path in relative_paths:
                self.assertTrue(
                    (ROOT / "skills" / skill_name / relative_path).is_file(),
                    f"missing {skill_name}/{relative_path}",
                )
```

- [ ] **Step 2: Run the inventory test and verify RED**

Run:

```bash
python3 -m unittest tests.test_bootstrap.PortableSkillInventoryTests -v
```

Expected: FAIL with `missing executing-plans/SKILL.md`.

- [ ] **Step 3: Install complete skill directories from the pinned commit**

Run the system skill-installer helper with the repository's `skills/` directory as its destination:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo obra/superpowers \
  --ref d884ae04edebef577e82ff7c4e143debd0bbec99 \
  --dest "$PWD/skills" \
  --path \
    skills/executing-plans \
    skills/subagent-driven-development \
    skills/using-git-worktrees
```

Expected: all three directories are installed without overwriting existing skills.

- [ ] **Step 4: Update the audited inventories**

Append the three names to the Superpowers `items` array in `sources.lock.toml`:

```toml
items = [
  "brainstorming",
  "writing-plans",
  "test-driven-development",
  "systematic-debugging",
  "verification-before-completion",
  "requesting-code-review",
  "receiving-code-review",
  "finishing-a-development-branch",
  "executing-plans",
  "subagent-driven-development",
  "using-git-worktrees",
]
```

Update `plugins.lock.toml` to state that execution and worktree workflows are included in the selectively vendored distribution while `enabled = false` remains unchanged. Add the same three names and concise descriptions to README's “Superpowers workflow subset.”

- [ ] **Step 5: Run the inventory test and verify GREEN**

Run:

```bash
python3 -m unittest tests.test_bootstrap.PortableSkillInventoryTests -v
```

Expected: `Ran 1 test` and `OK`.

- [ ] **Step 6: Verify repository configuration and bootstrap portability**

Run:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
scripts/doctor.sh
tmp_home=$(mktemp -d)
HOME="$tmp_home" PYTHON=python3 scripts/bootstrap.sh --apply
test "$(readlink "$tmp_home/.agents/skills")" = "$PWD/skills"
rm -rf "$tmp_home"
git diff --check
```

Expected: validation reports 25 skills, all tests and doctor pass, bootstrap links the current clone's `skills/` directory, and the diff check is clean.

- [ ] **Step 7: Review and commit**

Confirm the diff contains only the three upstream skill payloads, inventory test, lock metadata, README, and approved documentation. Commit with:

```bash
git add README.md plugins.lock.toml sources.lock.toml tests/test_bootstrap.py \
  skills/executing-plans skills/subagent-driven-development skills/using-git-worktrees
git commit -m "feat: vendor portable execution skills"
```

After verification, fast-forward the original `codex-config` `main` branch to the worktree branch and confirm both worktrees are clean.

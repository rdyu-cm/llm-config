# Portable Superpowers Execution Skills Design

## Goal

Extend the portable `codex-config` skill set with the Superpowers plan-execution
workflows so a clone can expose them on another machine after bootstrap.

## Design

Vendor the complete upstream directories for these skills under `skills/`:

- `executing-plans`
- `subagent-driven-development`
- `using-git-worktrees`

`using-git-worktrees` is required by both execution workflows. At the pinned
commit, the complete `subagent-driven-development` payload includes its
implementer and combined task-reviewer prompts plus the `review-package`,
`sdd-workspace`, and `task-brief` helper scripts. No file will be copied from
Codex's mutable marketplace cache. The three helper scripts will retain
executable Git modes because the skill invokes them directly.

All three directories will come from the Superpowers commit already pinned in
`sources.lock.toml` (`d884ae04edebef577e82ff7c4e143debd0bbec99`). The source
lock, plugin policy, and README inventory will be updated to describe the
expanded audited subset. The pinned upstream MIT notice will be stored under
`licenses/` so the vendored distribution carries its required attribution.
The full Superpowers plugin remains disabled.

## Portability

The existing bootstrap link remains unchanged:

```text
~/.agents/skills -> <clone>/skills
```

After pulling the repository on another cluster, running
`scripts/bootstrap.sh --apply` and starting a new Codex task will expose the
vendored skills from that clone's path.

## Validation

Repository validation must discover unique frontmatter names for all three new
skills and verify that the required helper payloads exist and are executable.
It must continue validating every tracked TOML, agent, hook, and skill.
`scripts/doctor.sh` must pass. A clean temporary-home bootstrap smoke test will
verify that the portable `skills/` directory is linked through
`~/.agents/skills`. Git diff checks will verify that only the requested skill
payloads, inventories, and design/plan documentation changed.

## Non-goals

- Do not enable or install `superpowers@openai-curated` as a plugin.
- Do not commit marketplace caches or Codex machine state.
- Do not change the mandatory behavior of existing vendored skills.
- Do not add unrelated Superpowers skills.

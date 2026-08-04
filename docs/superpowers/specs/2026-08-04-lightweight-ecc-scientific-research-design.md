# Lightweight ECC Scientific Research Adaptation

## Goal

Add five provider-neutral scientific research skills derived from selected ECC workflows
without installing ECC's plugin, global instructions, agents, commands, hooks, rules,
memory runtime, dashboard, or MCP servers. Preserve this repository as the sole owner of
Claude Code and Codex policy, installation, and provider adaptation.

## Chosen Approach

Vendor small, rewritten skills and record ECC as an audited upstream source. This follows
the repository's existing treatment of OpenAI Skills, Superpowers, Vercel, Impeccable, and
Trail of Bits.

The rejected alternatives are:

- Installing ECC through its Claude plugin or Codex sync flow. Those write to the same
  discovery and configuration surfaces managed by this repository and would create two
  policy owners.
- Forking ECC. Maintaining its full multi-harness runtime and hundreds of unrelated
  components is disproportionate to five research workflows.

## Skill Set

### `scientific-research`

Adapt ECC's `deep-research` workflow into a source-agnostic scientific evidence workflow.
It decomposes a question, records search strategy, prioritizes primary literature and
authoritative datasets, reads key sources in full, and produces claim-level citations.

The skill distinguishes peer-reviewed work, preprints, reviews, official datasets, and
secondary reporting. It records DOI or stable identifiers when available, checks versions
and retractions when practical, separates fact from inference, identifies contradictory
evidence, and reports coverage gaps. It does not require Exa, Firecrawl, or any specific
MCP. Available local, browser, and documentation tools are selected at runtime.

Substantial research produces one durable cited Markdown artifact, stored where the
project already keeps research notes or documentation. Chat-only delivery remains
appropriate for small factual lookups. The workflow is complete only when every material
claim in the durable artifact is traceable to a source and the search coverage and gaps
are recorded.

### `research-eval`

Adapt ECC's `eval-harness` concepts for reproducible scientific and computational
evaluation. Each evaluation records the question or hypothesis, baseline, dataset and
environment identity, metrics, acceptance criteria, randomization controls, repeated-run
policy, uncertainty, subgroup analysis, and raw-result location.

The workflow separates exploratory from confirmatory analysis, warns about multiple
comparisons, and refuses to treat a single passing aggregate metric as sufficient evidence.
Every evaluation begins with one explicit question and ends with a recorded verdict that
answers that question, including inconclusive outcomes. It complements rather than
replaces the repository's general verification skill.

### `research-memory`

Adapt ECC's `unified-memory` trust model into a file-format and workflow skill only. It
defines inspectable Markdown notes for sources, experiments, decisions, negative results,
open questions, and cross-harness handoffs.

No executable runtime, automatic recall, session hook, global memory directory, or MCP
server is installed. Notes are unreviewed context, never policy or instructions. Important
claims must be rechecked against primary evidence before use. Projects choose where notes
live; the skill recommends a Git-ignored project-local research directory unless a team
explicitly reviews and versions selected notes.

### `research-compact`

Adapt ECC's strategic compaction concept for long research sessions. A compact preserves
the research question, scope, hypotheses, search coverage, strongest and contradictory
evidence, exclusions, experimental state, unresolved uncertainties, and next reproducible
action. It is manually invoked or triggered by a request to prepare a handoff; no lifecycle
hook injects it automatically.

The compact references existing specs, experiment notes, datasets, commits, and results
instead of duplicating them. It redacts credentials and sensitive participant or research
data and names the skills likely needed for the next session.

### `scientific-ml`

Adapt the research-relevant portion of ECC's `mle-workflow`. It focuses on dataset
provenance, leakage prevention, baselines, deterministic environments, seed and repeated-run
policy, ablations, calibration, error analysis, uncertainty, artifact identity, and exact
reproduction instructions.

Production serving, feature stores, canaries, online monitoring, and heavyweight MLOps are
out of scope unless the user's project already contains those systems. The skill prefers
the smallest experiment that can falsify the hypothesis and requires disclosure of
hyperparameter search and selection effects. Each experiment states the single question it
answers and records a verdict before another experiment begins.

## Source Governance

`sources.lock.toml` gains one ECC entry with:

- the official `https://github.com/affaan-m/ECC` repository;
- the exact upstream commit reviewed during vendoring;
- MIT license metadata;
- the upstream components used as design sources: `deep-research`, `eval-harness`,
  `unified-memory`, `strategic-compact`, and `mle-workflow`;
- the five local adapted skill names.

The local files are adaptations rather than mirrored copies. Their headers identify ECC as
the design source and state that local scientific requirements take precedence.

`capability-bundle.toml` catalogs all five skills as supported shared components. They use
the same direct-child skill discovery paths as the existing library, so both Claude Code
and Codex receive one common copy.

## Update Review Helper

Add `scripts/review_ecc_updates.py`, a read-only helper invoked by
`scripts/update.sh --review ecc` or directly. It accepts the lock file and an optional
upstream revision for offline testing, resolves ECC `HEAD` when no revision is supplied,
and prints:

- pinned and candidate commit IDs;
- changed paths only under the five reviewed ECC source directories;
- whether each change is added, modified, deleted, or renamed;
- a clear message when unrelated ECC paths changed but none of the adopted sources did;
- the exact manual next steps, without modifying the checkout or lock file.

The helper uses a temporary shallow Git repository outside the project, fetches only the
pinned and candidate commits, and removes the temporary directory on exit. Network,
missing commits, and malformed lock data fail closed with a nonzero exit and actionable
diagnostics. It never copies files, updates a pin, or applies patches.

The existing no-argument `scripts/update.sh` behavior remains unchanged. `--apply` remains
rejected. The new `--review ecc` mode is opt-in so routine update checks stay concise.

## Validation and Tests

Extend repository validation and tests to require:

- all five skill directories and matching frontmatter names;
- all five capability-catalog entries;
- an ECC source with a full 40-character hexadecimal commit and the exact reviewed item
  list;
- no ECC plugin, hook, command, rule, agent, dashboard, MCP, or automatic-memory component
  in the capability catalog;
- update-review path filtering that includes only the five adopted upstream directories;
- read-only behavior: tests use local temporary Git repositories and assert that the source
  checkout, lock file, and working tree remain unchanged;
- useful failures for missing source entries and unavailable revisions.

Existing validator, unit, shell-syntax, and bootstrap dry-run checks remain the final
regression suite.

## Documentation

The README gains a compact Scientific Research section naming the five skills, explaining
that they are selective ECC adaptations, and documenting the manual review command. It
must state that updates are detected but never applied automatically.

## Non-Goals

- A scientific-writing skill
- ECC's Tkinter dashboard or a replacement dashboard
- Scholarly database, citation-manager, or journal-specific integrations
- Automatic memory recall or continuous learning
- Parallel research agents
- ECC installation, synchronization, or repair tooling
- Changes to the existing model routing, sandbox, hooks, MCP servers, or profiles

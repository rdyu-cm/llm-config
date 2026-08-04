---
name: scientific-research
description: Research scientific questions against primary literature, authoritative datasets, standards, and institutional sources; use for literature synthesis, evidence review, or current scientific claims requiring citations.
---

# Scientific Research

Adapted from ECC `deep-research` at
`7a5757e6c0d7e8e1080d30169b4b044d76e0f7fc`. This local scientific workflow
takes precedence over the upstream general-purpose workflow.

## Establish the question

State the research question, intended decision or output, scope, timeframe, and
field-specific terminology. Break broad questions into a small set of answerable
subquestions. Record material assumptions before searching.

## Search with provenance

Use the available browser, documentation, repository, or database tools; no particular MCP
is required. Record databases or search surfaces, exact queries, filters, and search date.
Prefer sources in this order when appropriate:

1. Primary peer-reviewed studies, official datasets, standards, and first-party technical
   documentation.
2. Systematic reviews and well-scoped meta-analyses.
3. Preprints, clearly labeled as not peer reviewed.
4. Secondary reporting only for discovery or context.

For important sources, read the full accessible work rather than relying on snippets or
abstracts. Capture DOI or another stable identifier, version, publication status, and any
known correction, withdrawal, or retraction. Never invent a citation or infer that a source
supports a claim from its title alone.

## Evaluate the evidence

For every material claim, record the supporting source and distinguish reported fact,
author interpretation, and your inference. Assess study design, sample or dataset,
measurement validity, uncertainty, relevant bias, conflicts of interest, and applicability.
Actively seek contradictory evidence. A single source is uncorroborated evidence, not
consensus. Absence of evidence is not evidence of absence.

## Synthesize

Report findings by subquestion, with claim-level citations. Separate peer-reviewed work,
preprints, reviews, datasets, and secondary material. State confidence and why, unresolved
disagreements, excluded evidence with reasons, and important coverage gaps.

For substantial work, save one durable cited Markdown artifact where the project already
keeps research notes or documentation; use a sensible project-local location if no
convention exists and tell the user where it was written. Small factual lookups may remain
in chat.

## Completion gate

Research is complete only when every material claim in the durable artifact is traceable
to a source, the search strategy is reproducible enough to repeat, contradictory evidence
is represented fairly, and limitations and coverage gaps are explicit.

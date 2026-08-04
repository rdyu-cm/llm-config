---
name: research-eval
description: Design or assess reproducible scientific and computational evaluations; use for hypotheses, benchmarks, experiments, model comparisons, metrics, uncertainty, or result interpretation.
---

# Research Evaluation

Adapted from ECC `eval-harness` at
`7a5757e6c0d7e8e1080d30169b4b044d76e0f7fc`. This local workflow targets
scientific evidence rather than general agent-product evaluation.

## Evaluation contract

Begin with one explicit question or falsifiable hypothesis. Record whether the work is
exploratory or confirmatory, the baseline or control, acceptance criteria, unacceptable
failure modes, and the decision the evidence may change. Do not choose success criteria
after seeing the result without labeling that analysis exploratory.

Identify datasets and splits by stable version or content hash, the execution environment,
software and hardware that can affect results, preprocessing, randomization, seeds, and the
location of raw outputs. Specify repeated-run policy before execution when stochasticity
matters.

## Measures and validity

Choose metrics from the scientific question, not convenience. Define units, aggregation,
uncertainty estimates, subgroup or slice analysis, and missing-data handling. Compare with
the baseline and report effect sizes alongside significance where applicable. Flag multiple
comparisons, selective reporting, leakage, dependent observations, and metric changes.

## Execute and preserve

Keep inputs immutable, retain machine-readable raw results, and make derived tables and
figures reproducible from them. Record deviations from the evaluation contract. A single
passing aggregate metric cannot establish robustness.

## Completion gate

End with a recorded verdict that directly answers the original question: supported,
not supported, or inconclusive. Include uncertainty, failed cases, subgroup differences,
deviations, and the evidence needed to change the verdict. Use
`verification-before-completion` separately for software correctness claims.

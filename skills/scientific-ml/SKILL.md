---
name: scientific-ml
description: Design, run, review, or reproduce scientific machine-learning experiments with explicit hypotheses, provenance, leakage controls, baselines, ablations, uncertainty, and artifact identity.
---

# Scientific Machine Learning

Adapted from ECC `mle-workflow` at
`7a5757e6c0d7e8e1080d30169b4b044d76e0f7fc`. The local workflow emphasizes
scientific reproducibility and omits production MLOps unless the project already requires it.

## Frame one experiment

State the single question the experiment answers, the falsifiable hypothesis, the baseline
or control, the scientific and guardrail metrics, expected failure costs, and the smallest
experiment capable of changing the current belief. Label exploratory work explicitly.

## Freeze provenance

Identify raw data origin, license or access restrictions, inclusion and exclusion rules,
dataset snapshot or content hash, preprocessing, label provenance and timing, split policy,
software environment, hardware-sensitive settings, random seeds, and artifact locations.
Test for duplicates, train/test contamination, temporal leakage, target leakage, and
preprocessing fitted outside the training partition.

## Compare fairly

Establish a simple baseline before adding complexity. Hold evaluation data and metrics
stable across comparisons. Record hyperparameter search space, budget, stopping rule, model
selection procedure, and every result used to choose the reported model. Use ablations to
test whether claimed contributions cause the improvement. Report calibration, error
clusters, subgroup behavior, compute cost, repeated-run variation, and uncertainty rather
than only the best run.

## Preserve reproduction

Save immutable configuration, dependency lock or environment identity, code revision,
dataset and artifact hashes, exact commands, raw metrics, and figure-generation steps.
Unsafe or nonportable model serialization must be called out. Use `research-eval` for the
evaluation contract and `scientific-research` for prior-art claims.

Production serving, feature stores, online monitoring, canaries, and retraining systems are
included only when already present in the user's scope. Do not introduce them to make a
research experiment look production-ready.

## Completion gate

Before beginning another experiment, record a verdict answering the original single
question: supported, not supported, or inconclusive. The verdict cites reproducible
artifacts, uncertainty, failed cases, selection effects, and the next hypothesis rather
than merely reporting the highest metric.

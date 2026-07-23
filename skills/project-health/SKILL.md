---
name: project-health
description: Use when asked to assess repository health or run its full native verification suite; diagnose with existing tools and report evidence without changing code.
---

# Project Health

## Purpose

Assess a repository using the project's own checks. This is a read-only diagnostic workflow. Do not edit code, install a new toolchain, or fix findings unless the user separately requests fixes.

## Discover the native checks

Read the repository instructions and inspect its manifests, task runner, and continuous-integration configuration. Identify the existing:

- formatter or formatting check;
- linter;
- type checker;
- unit and integration tests;
- build, documentation, security, or static-analysis checks that are part of normal development.

Do not invent commands when the repository already defines them. Avoid dependency installation unless the user authorized it and the checks cannot run otherwise.

## Run narrow to broad

Start with cheap configuration and targeted checks, then run broader suites when justified. Prefer non-mutating modes such as formatter checks over automatic formatting. Preserve exact exit codes and the smallest useful failure excerpts.

Distinguish among:

- a product failure;
- a test or configuration failure;
- a missing dependency or unavailable external service;
- a check that was intentionally skipped and why.

## Report

Lead with the overall health result. List each command run, whether it passed, and actionable evidence for failures. Separate verified findings from hypotheses and identify the smallest next diagnostic step. Stop after the report unless the user separately requests fixes.

Do not assign an arbitrary score, add telemetry, or introduce a dashboard.

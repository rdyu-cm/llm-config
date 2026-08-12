---
name: unit-test-design
description: Use when writing, reviewing, or repairing unit tests - choosing what behavior to assert, which inputs to cover, and proving a test can actually fail. Complements test-driven-development, which governs test order rather than test quality.
---

# Unit Test Design

## Overview

A unit test is an experiment. It states a falsifiable claim about behavior, and the run is the attempt to refute it. A test that no realistic defect could break is not a test - it is decoration that costs maintenance and returns confidence it never earned.

**Core principle:** every test must name a defect it would catch. If you cannot state that defect in one sentence, do not write the test.

`test-driven-development` governs *order* (test first, watch it fail). This skill governs *content*: what to assert, which inputs to pick, and whether the assertion is capable of failing.

## The Falsifiability Gate

```
BEFORE writing or keeping any test, answer:

  1. CLAIM       What guarantee of the contract does this pin down?
  2. REFUTATION  What single-line change to production code makes this test fail?
  3. DISCRIMINATION  Does it fail for ONLY that reason?

  Cannot name a concrete code change for (2):
    STOP - the test asserts nothing. Delete it or replace it.

  Unrelated refactors break it in (3):
    STOP - it measures structure, not behavior. Move the assertion to the public API.
```

Worked example:

- Claim: withdrawing more than the balance leaves the balance unchanged and returns `InsufficientFunds`.
- Refutation: changing `if amount > balance` to `if amount > balance + 1` fails it.
- Discrimination: renaming the internal ledger field does not fail it.

## Not a Test: The Usual Impostors

Test-shaped code that cannot fail meaningfully.

| Impostor | What it looks like | Why it is not evidence | Test this instead |
|---|---|---|---|
| **Config echo** | `assert os.environ["MODE"] == "prod"`, `assert Config.TIMEOUT == 30` | Restates a literal. Fails only when someone edits the constant - a rename detector | The behavior the value drives: a request aborts once the configured timeout elapses |
| **Tautology** | `assert total(a, b) == a + b` | Reimplements the code under test inside the assertion. Both sides share the bug | A hand-computed literal: `assert total(2, 3) == 5` |
| **Assertion-free** | Calls the function, asserts nothing, or only "did not raise" | "No exception" is the weakest property there is | The returned value and the state change |
| **Mock theater** | `expect(repo.save).toHaveBeenCalled()` | Verifies the test's own wiring, not the system. See `test-driven-development/testing-anti-patterns.md` | Observable state after the call, or the effect at the real boundary |
| **Framework test** | Asserts the ORM persists a row, or that `sort` sorts | Not your code, not your contract | Your mapping, your comparator, your query |
| **Blob snapshot** | Whole-object golden file, regenerated with `-u` whenever it goes red | Fails on every change, discriminates none of them | Targeted assertions on the fields the behavior owns |
| **Coverage filler** | Written to move a percentage; asserts whatever was convenient | Executes lines without checking consequences | Delete it, or give it a claim |

**Rule:** if the assertion restates the implementation, restates a literal, or observes the test's own scaffolding, it is not evidence.

## Designing a Test

### 1. Name a behavior, not a method

A behavior is a guarantee the system makes: *given* a state, *when* an action occurs, *then* an outcome holds. One method may host a dozen behaviors; one behavior may span several methods.

The name is the claim. It should read like the first line of a bug report.

<Good>
`withdraw_more_than_balance_leaves_balance_unchanged`
`retries_three_times_then_propagates_the_last_error`
</Good>

<Bad>
`test_withdraw`, `test_retry_2`, `test_BUG_4471`
</Bad>

### 2. Partition the input domain

Do not sample arbitrarily and do not enumerate exhaustively. Split the input domain into classes where the same rule should apply, then test the edges between them.

- **One case per equivalence class.** More is redundant; fewer leaves a hole.
- **Both sides of every boundary, plus the boundary itself:** `min-1, min, min+1` and `max-1, max, max+1`. Off-by-one errors live nowhere else.
- **The classes people forget:** empty, exactly one element, duplicates, `null`/`None`, zero, negative, maximum value, whitespace-only and non-ASCII strings, already-sorted and reverse-sorted input, and calling the same operation twice.
- **Vary one dimension per test.** Two variables at once means a failure does not localize.

For `discount(order_total, member_years)` with a 10% break at $100 and a loyalty tier at 2 years:

| Class | Input | Expected |
|---|---|---|
| Below break | `(99.99, 0)` | no discount |
| At break | `(100.00, 0)` | 10% |
| Just over | `(100.01, 0)` | 10% |
| Loyalty boundary | `(50, 2)` | tier applies |
| Just under loyalty | `(50, 1)` | tier does not apply |
| Invalid | `(-1, 0)` | rejects with `ValueError` |

When the classes multiply combinatorially, or the contract is algebraic (roundtrip, idempotence, invariant), switch to the `property-based-testing` skill instead of enumerating.

### 3. Choose what to observe

- **State over interactions.** Observe what the system looks like after the call. Reserve interaction assertions for effects with no observable state (an email dispatched, a card charged), and assert them at the boundary rather than on an internal call path.
- **Public API over internals.** Exercise the code the way its callers do. Tests reaching into private fields break on harmless refactors and pin down nothing a user depends on.
- **Complete and concise.** The body contains everything a reader needs to understand the result, and nothing else. Inputs that affect the outcome are visible in the test; the rest come from a builder default.
- **One reason to fail.** Several assertions describing one behavior are fine (`returns InsufficientFunds` *and* `balance unchanged`). Several assertions describing three behaviors are three tests.
- **No logic in tests.** No loops, conditionals, or arithmetic mirroring the implementation. Straight-line code with literal expected values. Needing a test for your test means the test is wrong.
- **DAMP over DRY.** Accept duplication that carries meaning. Helpers construct values; they do not hold assertions.
- **The failure message must identify the defect** without opening the test file.

### 4. Prove it discriminates - mutate the code

Coverage says a line executed. It does not say anything checked the consequence, and that gap is the standard failure mode of a green suite.

**Manual mutation (always available, takes seconds):** break the logic the test claims to cover, then re-run.

- flip `>` to `>=`
- swap `+` and `-`
- negate a boolean
- delete a guard clause
- return a constant instead of the computed value
- remove the error path

The test must go red. A surviving mutant is a hole in the assertion, not a hole in coverage.

**Automated:** PIT (JVM), Stryker (JS/TS/C#/Scala), mutmut or cosmic-ray (Python), cargo-mutants (Rust), go-mutesting (Go).

**Coverage:** use it to *find untested code*, never as a target. Once a percentage becomes a goal, tests get written to raise it, and those are exactly the tests that assert nothing.

## Properties Every Unit Test Needs

Beck's rule: no property should be given up without receiving a property of greater value in return.

| Property | Concrete check | Fix when violated |
|---|---|---|
| **Deterministic** | Same inputs produce the same result on every run, machine, and timezone | Inject a clock and a seed. Eliminate wall-clock reads, unseeded randomness, locale/timezone dependence, network and DNS, unordered map/set iteration, sleep-based waits, hardcoded ports |
| **Isolated** | Passes alone, in reverse order, and when repeated | Remove shared mutable state, global registries, leaked temp dirs and DB rows |
| **Behavioral** | Changing behavior changes the result | Assert consequences, not calls |
| **Structure-insensitive** | Pure refactoring keeps it green | Test through the public API |
| **Specific** | One failure points at one cause | Split the test; improve the assertion message |
| **Fast** | No network, no real database, no sleeping | Wrong level - move it to the integration suite rather than mocking the world |
| **Predictive** | A green suite means the code is deployable | Name what green does not cover, and close it |

A flaky test is worse than no test: it teaches the team that red means "run it again."

## Regression Tests for Bug Fixes

1. **Reproduce** the failure in a test before touching the fix. The test must fail on the pre-fix code *for the reason the bug occurred* - not from a typo or missing fixture.
2. **Minimize** the setup. Delete a line; if it still fails, leave it deleted. Every remaining element must be load-bearing.
3. **Name it after the behavior,** not the ticket. `BUG-4471` tells a future reader nothing; put the ticket in a comment.
4. **Fix, then confirm** the test flips to green and the rest of the suite stays green.

## Review Checklist

- [ ] Every test name states a behavior, not a method or a number
- [ ] For each test, a one-line production change that would fail it can be named
- [ ] Assertions observe public API and state - not internals, mocks, or constants
- [ ] Input classes cover nominal, both sides of each boundary, empty/null/zero/negative, and the error path
- [ ] One variable per test; a failure localizes to one cause
- [ ] No conditionals, loops, or implementation-mirroring expressions in test bodies
- [ ] Clock, randomness, ordering, locale, and I/O are controlled
- [ ] Suite passes alone, in reverse order, and on repeat
- [ ] Error cases assert the specific error and message, not merely "it raises"
- [ ] Failure output identifies the cause without opening the test file
- [ ] At least one mutant of the changed logic was introduced and killed

## Red Flags

- "It passed the first time I ran it" - it may not be able to fail
- Assertion restates the expression under test
- Test asserts an environment variable, a constant, or a config literal
- `expect(...).toHaveBeenCalled()` is the only assertion
- Snapshot regenerated to make the build green
- Test name contains "and", or a ticket number, or an index
- Setup is longer than the assertion and no line can be explained
- Test written after the fact to raise coverage
- Retried, `@flaky`, or skipped rather than diagnosed
- Refactoring with no behavior change broke tests

## Related Skills

| Skill | Use it for |
|---|---|
| `test-driven-development` | Order: failing test first, minimal code, verified red then green |
| `test-driven-development/testing-anti-patterns.md` | Mock-specific failures: testing mock behavior, test-only production methods, incomplete mocks |
| `property-based-testing` | Input spaces too large to enumerate, and algebraic contracts (roundtrip, idempotence, invariants) |
| `systematic-debugging` | Reproducing a failure before writing the regression test |
| `verification-before-completion` | Running the suite and quoting the evidence before claiming done |

## Sources

Aggregated from established testing guidance:

- [Kent Beck, Test Desiderata](https://testdesiderata.com/) - the twelve properties and their tradeoffs
- [Software Engineering at Google, ch. 12: Unit Testing](https://abseil.io/resources/swe-book/html/ch12.html) - unchanging tests, behaviors not methods, state over interactions, DAMP over DRY, no logic in tests
- [Google Testing Blog, Code Coverage Best Practices](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html) - coverage as a diagnostic rather than a target
- [Practical Mutation Testing at Scale: A View from Google](https://homes.cs.washington.edu/~rjust/publ/practical_mutation_testing_tse_2021.pdf) - mutation as the direct measure of test strength
- [PIT Mutation Testing](https://pitest.org/) - mutation operators, and the tooling reference
- Equivalence partitioning and boundary value analysis, standard test-design techniques ([overview](https://www.geeksforgeeks.org/software-testing/software-testing-boundary-value-analysis-vs-equivalence-partitioning/))

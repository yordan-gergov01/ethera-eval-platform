# Carrier: comparison

Constrains Baselines, Candidates, Comparisons, Gate Verdicts and Recommendations. All rules
here are pure domain logic, reused by the API and the CLI.

## Invariants

| ID | Rule | Status |
|---|---|---|
| INV-CMP-01 | A Candidate differs from its Baseline configuration in **exactly one** Change. | accepted |
| INV-CMP-02 | Two Eval Runs are comparable only with the same Dataset version and judge configuration; otherwise the Comparison is refused with a reason. | accepted |
| INV-CMP-03 | The Gate Verdict fails **if and only if** at least one Golden is a regression (always pass → always fail) or has status error. Flaky Goldens go to a human and do not block. | accepted |
| INV-CMP-04 | Recommendation is **switch** only if the gate passes, always-pass Goldens are at least the Baseline's, and cost and p95 latency increases are within the Manifest's limits; **discuss** if quality improves but cost or latency is over its limit; otherwise **keep**, with the reason. | accepted |
| INV-CMP-05 | A Baseline is immutable; promoting creates a new one and keeps the old one. A promotion writes an audit row. | accepted |
| INV-CMP-06 | Comparison transitions per Golden: fixed (fail→always pass), regression (always pass→always fail), now flaky (→flaky), still failing (always fail→always fail). | accepted (names); exact mapping of every status pair: proposed — OQ-CMP-01 |
| INV-CMP-07 | The report lists still failing, now flaky, regressions, fixed, then pass rates (read from the bottom up). | accepted (brief §4, §7.6) |
| INV-CMP-08 | The CLI exits `1` only on a regression or an error. | accepted |
| INV-CMP-09 | Fixes outside the code appear in the report with their owner. | accepted |

## Events (candidates)

- `BaselinePromoted` — consumer: none planned → drop unless a slice gives it one.
- `ComparisonCompleted` → `RecommendationIssued` — consumer: notification. Proposed.
- `RegressionDetected` — consumer: notification (failed gate). Proposed.

## Open questions

- **OQ-CMP-01**: Transition for pairs the brief does not name (e.g. flaky → always pass,
  always pass → flaky, error → anything). Decides: owner at slice 004 Gate B.
- **OQ-CMP-02**: "Quality improves" for `discuss` — measured by always-pass count, pass rate,
  or both? Decides: owner at slice 004.

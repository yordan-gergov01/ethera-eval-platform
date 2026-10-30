---
name: add-metric
description: Add a Metric for one failure type — its declared evidence fields, threshold, rubric examples, and a test that fails the bad cases, passes the good ones, and proves the metric reads no other fields. New metrics are proposed policies until the owner accepts them.
---

# Add a Metric

One Metric per failure type; each gets only the evidence it needs.

## Steps

1. Confirm the Metric is accepted in `docs/evaluation-guideline.md`. If not, write it there as
   a **proposed** metric and stop until the owner accepts it.
2. Define, in the runner's metric registry:
   - `name`, the failure type it checks;
   - `evidence` — the exact fields it reads (e.g. `facts_used`, `retrieved_doc_ids`), nothing
     else;
   - `threshold` and how a verdict is reached; a verdict carries a **reason**;
   - rubric examples: at least two that must fail and two that must pass.
3. Tests (mirrored test file):
   - each rubric example yields the expected verdict and a non-empty reason;
   - **evidence isolation**: the metric receives an evidence object where every undeclared
     field raises on access; it must still produce its verdict;
   - determinism: the same evidence always yields the same verdict.
4. Append its label to the web label map (`Record<MetricName, Label>`).

## Output (fixed shape)

```
Metric: <name>  failure type: <type>  evidence: [<fields>]  threshold: <...>
Rubric: <n> fail cases ✓, <n> pass cases ✓; evidence isolation ✓; determinism ✓
```

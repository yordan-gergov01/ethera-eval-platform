# Carrier: evaluation

Constrains the meaning of the `evaluation` module (Datasets, Goldens, Metrics, Eval Runs,
Trials, Case Results). Execution of Trials happens in `runner`; the rules below bind both.

## Concepts

- **Golden** — input, expected outcome = **decision + the rule behind it**, failure type,
  optional context (accepted). A Golden that no code change can fix names an owner outside
  engineering (accepted, brief §4 and §6.3).
- **Dataset** — versioned and immutable; adding a Golden publishes a new version (accepted).
- **Metric** — one per failure type; each receives only the evidence it needs (accepted).
  Initial metrics (accepted, brief §7.4): `policy_correct` (decision and numbers vs expected;
  full policy context), `stays_in_docs` (facts used ⊆ retrieved documents; retrieval context
  only), `answer_relevancy` (lexical), `offers_human_when_unknown`. Thresholds: proposed in
  `docs/evaluation-guideline.md`.
- **Eval Run** — one Product configuration × one Dataset version × N Trials per Golden.
  N = 3 (accepted, brief §4 "every Golden runs three times").
- **Trial** — tagged with source `harness` (accepted).
- **Dataset** — one per Product (accepted, D-024 PP-208); version 1 created by the seed.
- **Golden fields** (accepted, D-024): input, expected decision, rule (plain text naming the
  policy and its source document), failure type, optional context, optional
  `expected_numbers`, optional `owner` (`engineering` | `support_content`),
  `unfixable_by_code` (true requires an owner other than `engineering`).
- **Decision** value set (accepted, D-024 PP-202; global for the PoC): `approve_return`,
  `deny_return`, `explain_return`, `approve_refund`, `deny_refund`, `report_status`,
  `answer_from_docs`, `escalate`.
- **Failure type** value set (accepted, D-024 PP-203): `date_math`, `refund_rules`,
  `invented_facts`, `out_of_docs`, `retrieval_miss`, `order_status_tool`.

## Invariants

| ID | Rule | Status |
|---|---|---|
| INV-EVAL-01 | Every Golden runs N = 3 Trials in an Eval Run. | accepted |
| INV-EVAL-02 | Case Result: all Trials pass → always pass; all fail → always fail; mixed → flaky; fewer results than the run's trial count → **error**. | accepted |
| INV-EVAL-03 | A flaky Golden with identical trial outputs is **judge-flaky**; with different outputs, **product-flaky**. | accepted |
| INV-EVAL-04 | A Dataset version never changes after publication; Goldens are never edited in place. | accepted |
| INV-EVAL-05 | A Trial that cannot produce a result is reported with an error code, never dropped. | accepted (brief §7.4) |
| INV-EVAL-06 | Every mock model call writes a spend row in the same transaction as the stored Trial result. | accepted (brief §7.4, Bible cost rule) |
| INV-EVAL-07 | Input, data version, AI configuration and result are versioned together on the Eval Run. | accepted (brief §4, estimation) |
| INV-EVAL-08 | A Golden "passes" a Trial iff every Metric applied to it passes. | proposed |

## Events (candidates)

- `DatasetVersionPublished` — dropped (no consumer; slice 002, D-024).
- `EvalRunRequested` — consumer: runner (via `EvalTrialBatchRequested` message). Proposed.
- `TrialCompleted` — consumer: evaluation (stores results). Proposed; may be subsumed by the
  `TrialBatchCompleted` message.
- `EvalRunCompleted` — consumer: comparison (Comparison against the Baseline). Proposed.

## Open questions

- **OQ-EVAL-01**: Trial batch granularity — one message per Golden, per Golden×trial, or per
  run? Decides: owner at slice 003 Gate B (contract).
- **OQ-EVAL-02**: Is a Metric "error" (judge could not decide) a failed Trial or a missing
  result (→ Case Result error)? Decides: owner at slice 003.

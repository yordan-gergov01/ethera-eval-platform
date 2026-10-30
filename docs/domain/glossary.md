# Glossary — the ubiquitous language

Source: brief §5. Every term here is **accepted** (given by the owner in the brief). Use the
term exactly — in code identifiers (snake_case / PascalCase forms of the same words), API
paths, UI labels and docs. The forbidden synonyms never appear in identifiers; in prose they
appear only to say they are forbidden.

A new term is added only as **proposed** with a date, and becomes accepted by an owner
decision recorded in `CLAUDE.md`.

| Term | Meaning | Code form | Forbidden synonyms | Owning module | Status |
|---|---|---|---|---|---|
| **Product** | An AI application Ethera runs for a client, identified by `client_id` + `project_id` | `Product` | App, Service, Bot (in code) | registry | accepted |
| **Manifest** | The Product's `eval.yaml`: Model Bindings, sandbox target, Dataset, Metrics, gate, candidate policy, allowed providers | `Manifest` | Config, Settings | registry | accepted |
| **Model Binding** | A role (generation, judge, embedding) bound to a provider and a **full model ID**, never an alias | `ModelBinding` | Model setting | registry | accepted |
| **Golden** | One evaluation case: input, expected outcome (decision + rule), failure type, optional context | `Golden` | Test case, Example | evaluation | accepted |
| **Dataset** | A versioned, immutable set of Goldens for one Product | `Dataset`, `DatasetVersion` | Test set | evaluation | accepted |
| **Metric** | A named check for one failure type, with the evidence it receives and a threshold | `Metric` | Score, Grader (as a type) | evaluation (definition), runner (execution) | accepted |
| **Judge** | The component that applies Metrics to a product output | `Judge` | Evaluator, Grader | runner | accepted |
| **Eval Run** | One evaluation of one Product configuration against one Dataset version, N Trials per Golden | `EvalRun` | Test run, Job (in the domain) | evaluation | accepted |
| **Trial** | One execution of one Golden inside an Eval Run | `Trial` | Repeat, Attempt | evaluation | accepted |
| **Case Result** | A Golden's status across its Trials: always pass, always fail, flaky, error | `CaseResult` | Outcome | evaluation | accepted |
| **Baseline** | The accepted Eval Run a Product is compared against; immutable | `Baseline` | Reference run | comparison | accepted |
| **Change** | Exactly one difference between a Candidate configuration and the Baseline configuration | `Change` | Diff, Variant | comparison | accepted |
| **Candidate** | A Product configuration with one Change applied, evaluated in a Sandbox | `Candidate` | Experiment | comparison (definition), model_watch (scheduling) | accepted |
| **Comparison** | Per-Golden transitions between two Eval Runs: fixed, regression, now flaky, still failing | `Comparison` | Diff report | comparison | accepted |
| **Gate Verdict** | pass or fail, decided only by regressions and errors | `GateVerdict` | Status, Check | comparison | accepted |
| **Recommendation** | switch, discuss or keep, from quality, cost and latency together | `Recommendation` | Suggestion | comparison | accepted |
| **Model Change** | A detected change: released, alias moved, deprecation announced, price changed, latency changed | `ModelChange` | Update | model_watch | accepted |
| **Notification** | A message asking a human to decide something, linked to the evidence | `Notification` | Alert (except as severity) | notification | accepted |

## Value sets (accepted, from the brief)

| Concept | Values |
|---|---|
| Model Binding role | `generation`, `judge`, `embedding` |
| Case Result status | `always_pass`, `always_fail`, `flaky`, `error` |
| Comparison transition | `fixed`, `regression`, `now_flaky`, `still_failing` |
| Gate Verdict | `pass`, `fail` |
| Recommendation | `switch`, `discuss`, `keep` |
| Model Change kind | `released`, `alias_moved`, `deprecation_announced`, `price_changed`, `latency_changed` |
| Flaky kind | `judge_flaky` (identical trial outputs), `product_flaky` (different outputs) |
| Trace source | `customer`, `harness` |

## Identity and access (platform core, template terms)

User, Role, Permission — unchanged from template_core. Endpoints check Permissions, never
Role names.

## Pairs where the UI word and the code word differ

None yet. Each pair is recorded here and in the ledger once, the day it appears.

# Carrier: registry

Constrains the meaning of the `registry` module. Terms: `docs/domain/glossary.md`. Status
labels: **accepted** (owner, brief) or **proposed** (assistant, awaiting the owner).

## Concepts

- **Product** — identified by `client_id` + `project_id` (accepted). Demo seed: client
  `acme`, project `support-bot`, a fictional footwear store's customer-support assistant
  (accepted, brief §6.1).
- **Manifest** — the Product's `eval.yaml`: Model Bindings, sandbox target, Dataset, Metrics,
  gate, candidate policy, allowed providers (accepted). Its cost and p95-latency limits feed
  the Recommendation (accepted, implied by INV-CMP-04).
- **Model Binding** — role ∈ {generation, judge, embedding}, provider, full model ID
  (accepted).

## Invariants

| ID | Rule | Status |
|---|---|---|
| INV-REG-01 | A Model Binding refers to a full model ID; an alias is rejected. | accepted |
| INV-REG-02 | A Candidate run is allowed only for providers in the Product's `allowed_providers`. | accepted (enforced where Candidates are scheduled; owned here as data) |
| INV-REG-03 | A Manifest change writes an audit row in the same transaction. | accepted (brief §7.7) |
| INV-REG-04 | How an alias is recognised (e.g. a catalog flag vs a naming rule) | proposed — open question OQ-REG-01 |

## Events (candidates; kept only with a consumer in the same change set)

- `ProductRegistered` — consumer: none planned yet → **drop unless a slice gives it one**.
- `ManifestChanged` — candidate consumer: model_watch (re-select affected Products). Proposed.

## Open questions

- **OQ-REG-01**: What makes a model ID an "alias" — a property in the model catalog fixture,
  or a syntactic rule? Decides: owner at slice 001 Gate B.
- **OQ-REG-02**: Is the Manifest edited through the API, or loaded only from `eval.yaml`
  files in the repository (or both)? Decides: owner at slice 001 Gate B.

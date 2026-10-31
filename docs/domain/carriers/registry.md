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
| INV-REG-04 | An alias is recognised by a per-provider full-ID rule kept as data; for provider `mock` the full-ID form is `mock-<family>-<size>-v<N>`; a provider without a rule is unknown and refused. | accepted (D-017, Fork B2) |
| INV-REG-05 | A Manifest has exactly one `generation` binding, at most one `judge` and at most one `embedding`. | accepted (D-017, PP-005) |
| INV-REG-06 | Every binding's provider is in the Manifest's `allowed_providers`. | accepted (D-017, PP-006) |
| INV-REG-07 | Manifests are numbered 1, 2, … per Product and never change; a replacement creates the next version and keeps the old; content equal to the current version creates nothing. | accepted (D-017, PP-007) |
| INV-REG-08 | A replacement names the version it replaces; a stale version is refused with a conflict. | accepted (D-017, PP-008) |
| INV-REG-09 | A Manifest's `product` section names the Product it is submitted for. | accepted (D-017, PP-012) |
| INV-REG-10 | A Product of a Client the caller is not a member of is indistinguishable from one that does not exist. | accepted (D-017, PP-004) |
| INV-REG-11 | Every Manifest version has exactly one audit row: `manifest_created` for version 1, `manifest_replaced` for every later one; details hold IDs, version numbers and section names, never content. | accepted (D-017, PP-010) |
| INV-REG-12 | Slice 001 defines the Manifest sections `product`, `bindings` and `allowed_providers` only; any other key is refused until the slice that consumes it defines it. | accepted (D-017, Fork B3) |
| INV-REG-13 | `client_id` and `project_id` are slugs (lower case, digits, `-`); `project_id` is unique within its Client. | accepted (D-017, PP-013) |
| INV-REG-14 | Products are created by the seed only in slice 001. | accepted (D-017, Fork B4) |

## Events (candidates; kept only with a consumer in the same change set)

- `ProductRegistered` — consumer: none planned yet → **drop unless a slice gives it one**.
- `ManifestChanged` — candidate consumer: model_watch (re-select affected Products). Proposed.

## Open questions

- **OQ-REG-01**: Resolved (owner, 2026-10-30, D-017): a syntactic per-provider rule (INV-REG-04).
- **OQ-REG-02**: Resolved (owner, 2026-10-30, D-017): through the API, validated, versioned and
  audited (Fork B1 = A).

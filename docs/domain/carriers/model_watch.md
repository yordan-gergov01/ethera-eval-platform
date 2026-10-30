# Carrier: model_watch

Constrains catalog snapshots, Model Changes, affected-Product selection and Candidate
scheduling.

## Invariants

| ID | Rule | Status |
|---|---|---|
| INV-MW-01 | A periodic task polls `ModelCatalogSource` per provider, diffs against the last snapshot, and emits Model Changes of kinds released, alias moved, deprecation announced, price changed, latency changed. | accepted |
| INV-MW-02 | Pre-filter: skip a Candidate when the new model is worse on the benchmarks relevant to the Product type **and** not cheaper. | accepted |
| INV-MW-03 | Each Model Change selects affected Products (same provider, same or adjacent model class, provider allowed) and schedules one Candidate per Product, under a concurrency limit. | accepted |
| INV-MW-04 | The fixture clock advances only through an admin endpoint / "Simulate" action protected by its own permission, and every advance writes an audit row. | accepted |
| INV-MW-05 | A deprecation within 30 days of its date raises a Notification with the deadline and a migration Candidate run. | accepted (brief §5, §6.9) |
| INV-MW-06 | Benchmark slugs map to provider model IDs through a mapping table. | accepted |

## Events (candidates)

- `ModelChangeDetected` — consumer: model_watch itself (Candidate scheduling). Proposed.
- `CandidateRunScheduled` — consumer: evaluation (requests the Eval Run). Proposed.

## Open questions

- **OQ-MW-01**: "Adjacent model class" — defined in the catalog fixture or by a rule?
  Decides: owner at slice 005.
- **OQ-MW-02**: Which benchmarks are "relevant to the Product type" for a support assistant?
  Decides: owner at slice 005.
- **OQ-MW-03**: Concurrency limit value. Decides: owner at slice 005 (proposed default 2).

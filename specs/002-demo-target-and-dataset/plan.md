# Plan: 002-demo-target-and-dataset

**Inputs:** `spec.md` (D-024), `contract.md` (D-025, with its erratum), `research.md`
(R-201..R-207), the sealed oracle `ethera-eval-core/tests/integration/evaluation/`
(`SEALED.md`; it never changes).

**How the waves run:** sequentially, one implementer each; a wave starts from the previous
wave's result. Then lenses, adjudication, fixes and the full gate.

## Wave 1: the `evaluation` module (backend)

1. `add-module` for `evaluation`: barrel, `MODULES.py` line after `REGISTRY`, layers and pure-
   domain contracts, prefix `eval_`, migration folder depending on registry `0001`.
2. Import contracts (R-203): `registry` never imports `evaluation`; `evaluation` reaches
   `registry` only through its barrel.
3. Registry barrel, appended (R-201): a connection-taking Product lookup for the seed and a
   membership-gated one with the same `PRODUCT_NOT_FOUND`.
4. Domain: Golden, Decision, failure type, owner value sets (StrEnums, so the web keys on
   generated unions); validation of seeded and arranged Goldens (PP-202, PP-205).
5. Tables `eval_datasets`, `eval_dataset_versions`, `eval_goldens`: `client_id` NOT NULL, RLS
   ENABLE + FORCE, append-only for the runtime role (INV-EVAL-04), Product FK (R-202).
6. Repositories with explicit client filters on every query and JOIN; tenant-isolation tests
   per function, filter and row security each proven alone.
7. Services and API: the two endpoints of contract §2.1–2.2; error codes `DATASET_NOT_FOUND`,
   `DATASET_VERSION_NOT_FOUND`; plain-string `{number}` segment (C-205); no audit (C-213).
8. Seed: the 19 Goldens of contract §3.5 through the module seed hook.
9. `tests/integration/evaluation_fixtures.py`: `arrange_dataset_version` (§6).
10. R-207: narrow the registry route test; an evaluation route-Permission test.
11. Membership-gate coverage: any `evaluation/services/access.py` joins `CRITICAL_PATHS`.
12. Done when the Dataset half of the oracle passes (seed, versions, tenancy, backend
    never-log) plus the wave's own tests.

## Wave 2: the demo target

1. `demo_target/` package (R-204): FastAPI app factory from a configuration; own
   `requirements/demo_target.in` compiled into `dev.in`; documents and instruction sets
   (`v1.md`, `v2.md`, read on every construction) as package data; packaging, ruff, mypy,
   coverage and import-linter scopes; contract "demo_target imports nothing from the repo".
2. Behaviour rules R1–R6 (PP-206), prices and latency (C-209, C-210, R-205), refusals (C-206,
   C-211), logging (R-206, C-214).
3. Its own golden-sample tests per instruction set (FR-207) and the decision-set equality test
   with the backend (PP-202).
4. `evaluation_fixtures.py`: `demo_target_client`, `demo_target_logs` (§6).
5. Test image copies `demo_target/`; `.dockerignore` re-includes it (the FIX-006 seal checks).
6. Done when the whole oracle passes: 54 of 54.

## Wave 3: web

1. Feature `evaluation` (PP-210): API client, query keys, paths, label maps for decision,
   failure type and owner keyed on the generated unions; `FEATURES` gains it.
2. Product page composes the Dataset summary beside the Product detail (no feature imports).
3. Dataset page with a version selector, per `mockup.html`.
4. Regenerated `openapi.json` and `schema.gen.ts`; Vitest for the API client and label maps.

## After the waves

Lenses (security-privacy, house-rules, functional-spec, domain-guard) → adjudicator → fixes
with sealing tests → `full-gate` → report. Commit only on the owner's instruction (D-023).

# Research: 002-demo-target-and-dataset

Recon (Bible Phase 1) by the recon scout on 2026-11-01, after Gate B part 1 (D-024). Anchors
are in the scout's report; this file keeps what the contract and the plan rest on.

## Findings

1. **Module seeds run in `MODULES` order, each committed on its own** (`backend/core/startup.py`
   `run_module_seeds`). `evals/MODULES.py` becomes `(REGISTRY, EVALUATION)`; the evaluation
   seed finds `acme / support-bot` because the registry seed has committed. Seeds run as the
   migration owner, so row security is not exercised there.
2. **The registry barrel offers no Product lookup** (`__all__ = ["REGISTRY", "create_product",
   "demo_document"]`), and its read service opens its own tenant transaction.
3. **Nested tenant transactions are a hazard**: inside an open transaction a nested
   `in_transaction()` is a savepoint, so an inner `set_config(…, true)` would replace the outer
   transaction's Client set. Evaluation must not call a registry service that opens its own
   transaction from inside its own.
4. **No import-linter contract keeps one module to another's barrel.** Today
   `evals.evaluation` could import `evals.registry.services` and lint would pass.
5. **No `demo_target` exists**: no package, contract, requirements file, image or `sandbox`
   network. The header and length guards already name it; `root_packages`, packaging, mypy,
   ruff and coverage scopes do not.
6. **`tests/unit/evals/registry/api/test_router.py` goes red** once routes exist under
   `/api/v1/products/…/dataset` (prefix filter plus exact equality). It is not sealed.
7. **Shipped defect, fixed in this slice before the contract:** `.dockerignore` omitted
   `evals/`, so the backend images could not be built (FIX-006, confirmed with `docker build`).
8. **Gap:** module migrations have no "models and migrations agree" test; the existing one
   covers the core only. Recorded; not in this slice's scope.

## Decisions made here (reversible; reported at Gate B part 2)

| # | Decision | Why |
|---|---|---|
| R-201 | The registry barrel gains a connection-taking Product lookup (system path for the seed; a membership-gated one returning the same `PRODUCT_NOT_FOUND`), appended; evaluation opens one tenant transaction and passes it in | avoids finding 3 and a duplicated membership gate |
| R-202 | A Dataset references its Product by a foreign key to `registry.Product` (the first domain-to-domain key), with a migration dependency on registry `0001` | integrity; the context-map edge `evaluation → registry` allows it |
| R-203 | New import-linter contracts: `registry` never imports `evaluation`; `evaluation` imports `registry` only through its barrel; `demo_target` imports nothing from `backend`, `evals`, `runner`, `common_lib` | finding 4 and FR-208 |
| R-204 | `demo_target/` is a top-level package of `ethera-eval-core` with its own `requirements/demo_target.in` (FastAPI and uvicorn, already pinned for the backend), compiled into `dev.in`; its documents and instruction sets ship as package data; the test image copies it now (its tests run in the suite); its runtime image and compose service arrive in 003 (Fork D1 = A) | finding 5 |
| R-205 | `latency_ms` is derived from a stable digest (SHA-256) of model + question, never Python's salted `hash()` | contract §3.3 determinism across restarts |
| R-206 | The demo target logs one line per request with route, status and model only | contract C-214 |
| R-207 | `test_router.py`'s registry route test narrows its filter to the registry's own routes; evaluation gets its own route-Permission test | finding 6 |

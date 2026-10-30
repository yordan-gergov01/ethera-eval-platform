"""The product's domain: one package per bounded context, mounted into the platform core.

Role: namespace of the domain modules (registry, evaluation, comparison, model_watch,
  notification — candidates in docs/domain/context-map.md), each created by the `add-module`
  skill in the slice that first needs it.
Used by: `evals.app` (composition root) and the tests.
Depends on: the `backend` barrel only.
Key invariants: no module package exists until its slice (an empty module would be a dead
  seam, and import-linter refuses contracts naming missing modules — docs/DECISIONS.md D-003).
"""

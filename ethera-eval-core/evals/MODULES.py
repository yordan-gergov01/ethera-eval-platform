"""The append-only registry of mounted domain modules.

Role: the single list of domain modules the backend mounts — each entry carries the module's
  router, Tortoise models and migrations package (`backend.ModuleMount`).
Used by: `evals.app.create_app` and `evals.migration_cli`.
Depends on: the `backend` barrel; each module's barrel once it exists.
Key invariants: APPEND-ONLY — a new module adds one entry at the end; existing entries are
  never edited by another feature (Bible, cross-cutting registries, tier 1). Slice 001 added
  `registry` (docs/DECISIONS.md D-003).
"""

from backend import ModuleMount
from evals.registry import REGISTRY

MODULES: tuple[ModuleMount, ...] = (REGISTRY,)

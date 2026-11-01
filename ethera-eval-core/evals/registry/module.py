"""The registry as the core mounts it.

Role: `REGISTRY`, the registry's `ModuleMount`: its router, its Tortoise app `registry` with its
  models and migrations package, its startup seed and its append-only tables.
Used by: the `evals.registry` barrel, and through it `evals.MODULES`.
Depends on: the `backend` barrel (`ModuleMount`), `evals.registry.api`,
  `evals.registry.services` (the seed).
Key invariants: the app label `registry` and the table prefix `reg_` never change (D-007);
  both tables are append-only for the runtime role (INV-REG-07: Manifest versions never
  change; Products are only created in slice 001, INV-REG-14).
"""

from backend import ModuleMount
from evals.registry.api import router
from evals.registry.services import seed_demo_product

REGISTRY = ModuleMount(
    name="registry",
    router=router,
    models=("evals.registry.models",),
    migrations="evals.registry.migrations",
    seed=seed_demo_product,
    append_only_tables=("reg_products", "reg_manifests"),
)

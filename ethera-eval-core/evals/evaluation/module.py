"""The evaluation module as the core mounts it.

Role: `EVALUATION`, the evaluation module's `ModuleMount`: its router, its Tortoise app
  `evaluation` with its models and migrations package, its startup seed and its append-only
  tables.
Used by: the `evals.evaluation` barrel, and through it `evals.MODULES`.
Depends on: the `backend` barrel (`ModuleMount`), `evals.evaluation.api`,
  `evals.evaluation.services` (the seed).
Key invariants: the app label `evaluation` and the table prefix `eval_` never change (D-007);
  mounted after `registry`, whose seed creates the Product the Dataset seed needs (research
  finding 1). All three tables are append-only for the runtime role: a published Dataset
  version and its Goldens never change (INV-EVAL-04).
"""

from backend import ModuleMount
from evals.evaluation.api import router
from evals.evaluation.services import seed_demo_dataset

EVALUATION = ModuleMount(
    name="evaluation",
    router=router,
    models=("evals.evaluation.models",),
    migrations="evals.evaluation.migrations",
    seed=seed_demo_dataset,
    append_only_tables=("eval_datasets", "eval_dataset_versions", "eval_goldens"),
)

"""The evaluation module: Datasets and their Goldens (slice 002); Eval Runs arrive in 003.

Role: the module's barrel — its mount for `evals.MODULES` and the services other code may use
  (publishing a Dataset version the way the seed does).
Used by: `evals.MODULES`; tests/integration/evaluation_fixtures.py.
Depends on: `evals.evaluation.module`, `evals.evaluation.services`.
Key invariants: outsiders import this barrel only, never the module's layers.
"""

from evals.evaluation.module import EVALUATION
from evals.evaluation.services import publish_dataset_version

__all__ = ["EVALUATION", "publish_dataset_version"]

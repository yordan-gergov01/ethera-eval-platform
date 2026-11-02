"""Use cases of the evaluation module: reading Datasets, publishing versions, the demo seed.

Role: re-exports the evaluation module's services.
Used by: `evals.evaluation.api`, `evals.evaluation.module`, the `evals.evaluation` barrel.
Depends on: `evals.evaluation.services.datasets`, `.publishing`, `.seed`.
Key invariants: none.
"""

from evals.evaluation.services.datasets import (
    DatasetSummary,
    DatasetVersionDetails,
    get_dataset_summary,
    get_dataset_version,
)
from evals.evaluation.services.publishing import publish_dataset_version
from evals.evaluation.services.seed import seed_demo_dataset

__all__ = [
    "DatasetSummary",
    "DatasetVersionDetails",
    "get_dataset_summary",
    "get_dataset_version",
    "publish_dataset_version",
    "seed_demo_dataset",
]

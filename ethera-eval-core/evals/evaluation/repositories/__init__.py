"""Data access of the evaluation module: Datasets, Dataset versions and Goldens.

Role: re-exports the repositories and the records they return.
Used by: `evals.evaluation.services`; tests/integration/evals/evaluation/.
Depends on: `evals.evaluation.repositories.datasets`, `.goldens`, `.records`.
Key invariants: none.
"""

from evals.evaluation.repositories.datasets import DatasetRepository
from evals.evaluation.repositories.goldens import GoldenRepository
from evals.evaluation.repositories.records import DatasetRecord, GoldenRecord, VersionRecord

__all__ = [
    "DatasetRecord",
    "DatasetRepository",
    "GoldenRecord",
    "GoldenRepository",
    "VersionRecord",
]

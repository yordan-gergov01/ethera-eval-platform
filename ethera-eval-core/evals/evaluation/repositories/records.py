"""Frozen records the evaluation module's repositories return instead of ORM objects.

Role: `DatasetRecord`, `VersionRecord` (a version with its Golden count) and `GoldenRecord` (a
  Golden at its position).
Used by: `evals.evaluation.repositories.datasets`, `.goldens`; `evals.evaluation.services`;
  `evals.evaluation.api.schemas` (response mapping).
Depends on: `evals.evaluation.domain` (`Golden`).
Key invariants: immutable values. `published_at` is the version row's `created_at`, read from
  one place, so the summary and the version endpoint can never disagree about it.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from evals.evaluation.domain import Golden


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    """A Product's Dataset: its identity and its Client."""

    id: UUID
    client_id: str


@dataclass(frozen=True, slots=True)
class VersionRecord:
    """One published version of a Dataset, with how many Goldens it holds."""

    id: UUID
    number: int
    published_at: datetime
    golden_count: int


@dataclass(frozen=True, slots=True)
class GoldenRecord:
    """A Golden at its position (1..n) in its version."""

    position: int
    golden: Golden

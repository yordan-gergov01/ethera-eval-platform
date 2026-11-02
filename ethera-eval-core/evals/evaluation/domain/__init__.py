"""The evaluation domain: Goldens, their value sets, and Dataset version numbers.

Role: re-exports the pure domain the evaluation module's repositories, services and API use.
Used by: `evals.evaluation.repositories`, `evals.evaluation.services`,
  `evals.evaluation.api.schemas`; tests/unit/evals/evaluation/.
Depends on: `evals.evaluation.domain.values`, `.golden`, `.version_number`.
Key invariants: pure — no framework, ORM, broker, HTTP or logging import, no I/O, no clock
  (import-linter contract "The evaluation domain is pure").
"""

from evals.evaluation.domain.golden import Golden, InvalidGoldenError, count_failure_types
from evals.evaluation.domain.values import Decision, FailureType, GoldenOwner
from evals.evaluation.domain.version_number import parse_version_number

__all__ = [
    "Decision",
    "FailureType",
    "Golden",
    "GoldenOwner",
    "InvalidGoldenError",
    "count_failure_types",
    "parse_version_number",
]

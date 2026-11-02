"""The evaluation module's HTTP surface.

Role: re-exports the evaluation module's router.
Used by: `evals.evaluation.module`.
Depends on: `evals.evaluation.api.router`.
Key invariants: none.
"""

from evals.evaluation.api.router import router

__all__ = ["router"]

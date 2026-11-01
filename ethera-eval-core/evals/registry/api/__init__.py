"""The registry's HTTP surface.

Role: re-exports the registry's router.
Used by: `evals.registry.module`.
Depends on: `evals.registry.api.router`.
Key invariants: none.
"""

from evals.registry.api.router import router

__all__ = ["router"]

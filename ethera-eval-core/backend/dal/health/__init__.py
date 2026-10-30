"""Data access for the database health check.

Role: re-exports `DatabaseProbe` as the feature's public surface.
Used by: `backend.services.health.service`.
Depends on: `backend.dal.health.repository`.
Key invariants: none.
"""

from backend.dal.health.repository import DatabaseProbe

__all__ = ["DatabaseProbe"]

"""Data access for roles, permissions and grants.

Role: re-exports `RoleRepository` as the feature's public surface.
Used by: `backend.services.roles.service`, `backend.services.seeding.service`.
Depends on: `backend.dal.roles.repository`.
Key invariants: none.
"""

from backend.dal.roles.repository import RoleRepository

__all__ = ["RoleRepository"]

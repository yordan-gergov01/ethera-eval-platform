"""Roles and their permissions.

Role: re-exports `RoleDetails`, `RoleService` and `build_role_service` as the feature's public
  surface.
Used by: `backend.api.dependencies.services`, `backend.api.v1.roles.router`.
Depends on: `backend.services.roles.service`.
Key invariants: none.
"""

from backend.services.roles.service import RoleDetails, RoleService, build_role_service

__all__ = ["RoleDetails", "RoleService", "build_role_service"]

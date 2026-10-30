"""Roles and the permissions they grant, for choosing a role in the UI.

Role: `RoleService.list_roles` (every role, sorted by name, with its permissions as stored) and
  `build_role_service`.
Used by: `backend.services.roles` (re-export), and through it `backend.api.v1.roles.router`.
Depends on: `backend.dal.roles.RoleRepository` (behind the `GrantReader` Protocol),
  `common_lib.permissions.Permission`.
Key invariants: read-only; the grants come from the database (synced from code at startup by
  `backend.services.seeding`), not from `common_lib.permissions` directly.
"""

from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from backend.dal.roles import RoleRepository
from common_lib.permissions import Permission


class GrantReader(Protocol):
    async def grants(self) -> Mapping[str, set[str]]: ...


class RoleDetails(BaseModel):
    """A role and the permissions it currently grants."""

    model_config = ConfigDict(frozen=True)

    name: str
    permissions: list[Permission]


class RoleService:
    def __init__(self, roles: GrantReader) -> None:
        self._roles = roles

    async def list_roles(self) -> list[RoleDetails]:
        """Every role, by name, with its permissions as stored in the database."""
        grants = await self._roles.grants()
        return [
            RoleDetails(name=name, permissions=sorted(Permission(code) for code in codes))
            for name, codes in sorted(grants.items())
        ]


def build_role_service() -> RoleService:
    """Wire the service to the real repository."""
    return RoleService(roles=RoleRepository())

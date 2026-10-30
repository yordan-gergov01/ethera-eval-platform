"""Permissions and the roles that hold them by default.

Role: the `Permission` and `RoleName` enums and `DEFAULT_ROLE_GRANTS`. To add a permission: add
  a member to `Permission`, add it to the grants, and declare it on the endpoint; no migration
  is needed.
Used by: `backend.api.dependencies.permissions`, the roles and users routers, the auth, roles,
  seeding and users services, `common_lib.schemas.users`; tests/unit/common_lib/test_permissions.py.
Depends on: the standard library only.
Key invariants: the code is the source of truth: on every start the backend syncs these
  permissions, the roles and their grants into the database (template_core D-006). Endpoints
  check permissions, never role names; `RoleName` is for seeding and assignment only. The admin
  role holds every permission. Covered by the 100% auth coverage gate (D-008). ORM-free.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class Permission(StrEnum):
    """A named capability that an endpoint can require."""

    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"


class RoleName(StrEnum):
    """The built-in roles. Used for seeding and role assignment, never for access checks."""

    ADMIN = "admin"
    USER = "user"


DEFAULT_ROLE_GRANTS: Mapping[RoleName, frozenset[Permission]] = MappingProxyType(
    {
        RoleName.ADMIN: frozenset(Permission),
        # Granted permissions arrive with the features that need them.
        RoleName.USER: frozenset(),
    }
)

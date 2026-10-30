"""Roles, permissions and the grants that link them.

Role: the `PermissionRecord` and `Role` models (tables `permissions`, `roles`,
  `role_permissions`).
Used by: `common_lib.models` (re-export) and `common_lib.models.user` (the FK target).
Depends on: Tortoise.
Key invariants: these rows mirror `common_lib.permissions`, which is the source of truth; the
  backend syncs them on every start. `PermissionRecord` is named to avoid confusion with the
  `Permission` enum. Every user has exactly one role. Schema changes need a new migration in
  `migrations/`.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

if TYPE_CHECKING:
    from common_lib.models.user import User


class PermissionRecord(Model):
    """A stored permission. Named to avoid confusion with the `Permission` enum."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    code = fields.CharField(max_length=64, unique=True)

    roles: fields.ManyToManyRelation["Role"]

    class Meta:
        table = "permissions"

    def __str__(self) -> str:
        return self.code


class Role(Model):
    """A named set of permissions. Every user has exactly one role."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    name = fields.CharField(max_length=50, unique=True)
    permissions: fields.ManyToManyRelation[PermissionRecord] = fields.ManyToManyField(
        "models.PermissionRecord",
        related_name="roles",
        through="role_permissions",
        forward_key="permission_id",
        backward_key="role_id",
    )

    users: fields.ReverseRelation["User"]

    class Meta:
        table = "roles"

    def __str__(self) -> str:
        return self.name

"""Clients and Client Memberships: the core identity data tenancy is built on.

Role: the `Client` (table `clients`) and `ClientMembership` (table `client_memberships`) models.
Used by: `common_lib.models` (re-export), and through it `backend.dal.clients.repository`.
Depends on: Tortoise, `common_lib.models.user.User` (the membership's user).
Key invariants: `client_id` is the Client's slug and the tenant key every client-owned table
  carries (D-014); memberships reference it by that slug, so a member Client ID needs no join.
  Neither table has row security: memberships are read BEFORE any tenant is set, to decide
  which tenants to set (D-022 Fork R1 = A), and are guarded by Permissions instead. Both are
  create-only in slice 001 (no update or delete path). Schema changes need a new migration in
  `migrations/`.
"""

from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

from common_lib.models.user import User


class Client(Model):
    """An organisation Ethera evaluates products for; its `client_id` is the tenant key."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    client_id = fields.CharField(max_length=64, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "clients"

    def __str__(self) -> str:
        return self.client_id


class ClientMembership(Model):
    """A user's access to one Client. Staff get explicit memberships too (D-014)."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name=False, on_delete=fields.OnDelete.RESTRICT
    )
    client: fields.ForeignKeyRelation[Client] = fields.ForeignKeyField(
        "models.Client",
        related_name=False,
        to_field="client_id",
        on_delete=fields.OnDelete.RESTRICT,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "client_memberships"
        unique_together = (("user", "client"),)

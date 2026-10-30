"""User accounts.

Role: the `User` model (table `users`).
Used by: `common_lib.models` (re-export); `common_lib.models.role` references it for typing.
Depends on: Tortoise, `common_lib.models.role.Role`.
Key invariants: users are deactivated, never deleted (template_core D-007); the role FK is
  `RESTRICT`. Usernames and emails are stored normalised (lowercase), so uniqueness is
  effectively case-insensitive. `token_version` is increased on logout and password change,
  which invalidates every token issued before. UUIDv4 primary key. Schema changes need a new
  migration in `migrations/`.
"""

from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

from common_lib.models.role import Role


class User(Model):
    """A login account. Users are deactivated, never deleted.

    Usernames and emails are stored in lowercase; the request schemas normalise
    them, so uniqueness is effectively case-insensitive. `token_version` is
    increased on logout and password change, which invalidates every token
    issued before.
    """

    id = fields.UUIDField(primary_key=True, default=uuid4)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=254, unique=True)
    full_name = fields.CharField(max_length=200, default="")
    password_hash = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    token_version = fields.IntField(default=0)
    role: fields.ForeignKeyRelation[Role] = fields.ForeignKeyField(
        "models.Role",
        related_name="users",
        on_delete=fields.OnDelete.RESTRICT,
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return self.username

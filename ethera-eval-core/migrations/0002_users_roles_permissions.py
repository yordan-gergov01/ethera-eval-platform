"""Core migration 0002: the users, roles and permissions tables.

Role: creates `permissions`, `roles`, `role_permissions` and `users` for the models in
  `common_lib.models`.
Used by: Tortoise's migration runner, via `backend.core.startup.apply_migrations` and
  `evals.migration_cli`; 0003 depends on it.
Depends on: 0001; Tortoise's migration operations.
Key invariants: generated from the models and committed (template_core D-004); never edited once
  applied — a model change is a new revision. The `users.role_id` FK is `RESTRICT` (accounts and
  roles are never deleted). UUID primary keys.
"""

from uuid import uuid4

from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0001_enable_pgvector")]

    initial = False

    operations = [
        ops.CreateModel(
            name="PermissionRecord",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                ("code", fields.CharField(unique=True, max_length=64)),
            ],
            options={
                "table": "permissions",
                "app": "models",
                "pk_attr": "id",
                "table_description": "A stored permission. Named to avoid confusion with the `Permission` enum.",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Role",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                ("name", fields.CharField(unique=True, max_length=50)),
                (
                    "permissions",
                    fields.ManyToManyField(
                        "models.PermissionRecord",
                        unique=True,
                        db_constraint=True,
                        through="role_permissions",
                        forward_key="permission_id",
                        backward_key="role_id",
                        related_name="roles",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "roles",
                "app": "models",
                "pk_attr": "id",
                "table_description": "A named set of permissions. Every user has exactly one role.",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                ("username", fields.CharField(unique=True, max_length=50)),
                ("email", fields.CharField(unique=True, max_length=254)),
                ("full_name", fields.CharField(default="", max_length=200)),
                ("password_hash", fields.CharField(max_length=255)),
                ("is_active", fields.BooleanField(default=True)),
                ("token_version", fields.IntField(default=0)),
                (
                    "role",
                    fields.ForeignKeyField(
                        "models.Role",
                        source_field="role_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="users",
                        on_delete=OnDelete.RESTRICT,
                    ),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ("updated_at", fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={
                "table": "users",
                "app": "models",
                "pk_attr": "id",
                "table_description": "A login account. Users are deactivated, never deleted.",
            },
            bases=["Model"],
        ),
    ]

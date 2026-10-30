"""The models load and their relations resolve, without a database.

Role: pins common_lib.models (`User`, `Role`, `PermissionRecord`): explicit table names, the
  user's role as a required RESTRICT foreign key, the unique `role_permissions` link table,
  unique natural keys and UUID primary keys.
Used by: pytest (unit).
Depends on: Tortoise `init_models` (the module-scoped autouse `_init_models` fixture); no
  database.
Key invariants: inspects model metadata only, never connects; the schema actually created is
  covered by tests/integration/test_migrations.py.
"""

import pytest
from tortoise import Tortoise, fields

from common_lib.models import PermissionRecord, Role, User


@pytest.fixture(autouse=True, scope="module")
def _init_models() -> None:
    Tortoise.init_models(["common_lib.models"], "models")


def test_tables_are_named_explicitly() -> None:
    assert User._meta.db_table == "users"
    assert Role._meta.db_table == "roles"
    assert PermissionRecord._meta.db_table == "permissions"


def test_user_role_is_a_required_restricting_foreign_key() -> None:
    role_field = User._meta.fields_map["role"]

    assert isinstance(role_field, fields.relational.ForeignKeyFieldInstance)
    assert role_field.related_model is Role
    assert role_field.null is False
    assert role_field.on_delete == fields.OnDelete.RESTRICT


def test_role_permissions_use_a_unique_link_table() -> None:
    link = Role._meta.fields_map["permissions"]

    assert isinstance(link, fields.relational.ManyToManyFieldInstance)
    assert link.related_model is PermissionRecord
    assert link.through == "role_permissions"
    assert (link.backward_key, link.forward_key) == ("role_id", "permission_id")
    assert link.unique is True


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (User, "username"),
        (User, "email"),
        (Role, "name"),
        (PermissionRecord, "code"),
    ],
)
def test_natural_keys_are_unique(model: type[User | Role | PermissionRecord], field: str) -> None:
    assert model._meta.fields_map[field].unique is True


def test_ids_are_uuid_primary_keys() -> None:
    for model in (User, Role, PermissionRecord):
        assert isinstance(model._meta.pk, fields.UUIDField)

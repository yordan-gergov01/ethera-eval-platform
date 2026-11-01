"""Tortoise models of the registry: Products and their Manifest versions.

Role: `Product` (table `reg_products`) and `ManifestVersion` (table `reg_manifests`), the
  registry's Tortoise app `registry` (D-007).
Used by: Tortoise through `evals.registry.module` (`ModuleMount.models`);
  `evals.registry.repositories`.
Depends on: Tortoise; the core models `models.Client` and `models.User` by label.
Key invariants: both tables are client-owned: `client_id` (the Client slug) is NOT NULL, row
  security is ENABLED and FORCED with the tenant policy (migration 0001), and repositories
  filter on it explicitly too (D-014). A Product is unique per (`client_id`, `project_id`)
  (INV-REG-13). Manifest versions are immutable and append-only (INV-REG-07): the runtime role
  may only insert and read `reg_manifests` and `reg_products` (`ModuleMount.append_only_tables`);
  the unique (`product`, `version`) pair serialises concurrent replacements (INV-REG-08). A
  version's `client_id` is its Product's. Schema changes need a new migration in
  `evals/registry/migrations/`.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

if TYPE_CHECKING:  # only for annotations: a runtime import would register them in this app
    from common_lib.models import Client, User


class Product(Model):
    """An AI application Ethera runs for a Client."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    client: fields.ForeignKeyRelation["Client"] = fields.ForeignKeyField(
        "models.Client",
        related_name=False,
        to_field="client_id",
        on_delete=fields.OnDelete.RESTRICT,
    )
    project_id = fields.CharField(max_length=64)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "reg_products"
        unique_together = (("client", "project_id"),)


class ManifestVersion(Model):
    """One immutable version of a Product's Manifest."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    product: fields.ForeignKeyRelation[Product] = fields.ForeignKeyField(
        "registry.Product", related_name=False, on_delete=fields.OnDelete.RESTRICT
    )
    client: fields.ForeignKeyRelation["Client"] = fields.ForeignKeyField(
        "models.Client",
        related_name=False,
        to_field="client_id",
        on_delete=fields.OnDelete.RESTRICT,
    )
    version = fields.IntField()
    document = fields.TextField()
    bindings: fields.JSONField[list[dict[str, Any]]] = fields.JSONField()  # Any: JSON values
    allowed_providers: fields.JSONField[list[str]] = fields.JSONField()
    created_by: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name=False, on_delete=fields.OnDelete.RESTRICT
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "reg_manifests"
        unique_together = (("product", "version"),)

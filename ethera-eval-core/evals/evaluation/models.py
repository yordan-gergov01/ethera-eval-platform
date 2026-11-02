"""Tortoise models of the evaluation module: Datasets, their versions and their Goldens.

Role: `Dataset` (table `eval_datasets`), `DatasetVersion` (`eval_dataset_versions`) and
  `GoldenRow` (`eval_goldens`), the evaluation module's Tortoise app `evaluation` (D-007).
Used by: Tortoise through `evals.evaluation.module` (`ModuleMount.models`);
  `evals.evaluation.repositories`.
Depends on: Tortoise; the core model `models.Client` and the registry's `registry.Product` by
  label only (a Dataset references its Product by foreign key, R-202; never by import).
Key invariants: all three tables are client-owned: `client_id` (the Client slug) is NOT NULL,
  row security is ENABLED and FORCED with the tenant policy (migration 0001), and repositories
  filter on it explicitly too (D-014). One Dataset per Product (unique `product`, PP-208);
  version numbers are unique per Dataset and positions unique per version. All three tables are
  append-only for the runtime role (`ModuleMount.append_only_tables`): a published version and
  its Goldens never change (INV-EVAL-04), and there is no "current version" column — the current
  version is the highest number. A version's publication time is its `created_at`. A row's
  `client_id` is its Product's. Schema changes need a new migration in
  `evals/evaluation/migrations/`.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

if TYPE_CHECKING:  # only for annotations: a runtime import would register them in this app
    from common_lib.models import Client


class Dataset(Model):
    """The versioned set of Goldens of one Product."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    # One-to-one, not a unique foreign key: Tortoise drops `unique` on a ForeignKeyField
    # (test_second_dataset_for_one_product_is_refused).
    product: fields.OneToOneRelation[Model] = fields.OneToOneField(
        "registry.Product", related_name=False, on_delete=fields.OnDelete.RESTRICT
    )
    client: fields.ForeignKeyRelation["Client"] = fields.ForeignKeyField(
        "models.Client",
        related_name=False,
        to_field="client_id",
        on_delete=fields.OnDelete.RESTRICT,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_datasets"


class DatasetVersion(Model):
    """One immutable, numbered version of a Dataset."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    dataset: fields.ForeignKeyRelation[Dataset] = fields.ForeignKeyField(
        "evaluation.Dataset", related_name=False, on_delete=fields.OnDelete.RESTRICT
    )
    client: fields.ForeignKeyRelation["Client"] = fields.ForeignKeyField(
        "models.Client",
        related_name=False,
        to_field="client_id",
        on_delete=fields.OnDelete.RESTRICT,
    )
    number = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_dataset_versions"
        unique_together = (("dataset", "number"),)


class GoldenRow(Model):
    """One Golden of one Dataset version, at its position."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    version: fields.ForeignKeyRelation[DatasetVersion] = fields.ForeignKeyField(
        "evaluation.DatasetVersion", related_name=False, on_delete=fields.OnDelete.RESTRICT
    )
    client: fields.ForeignKeyRelation["Client"] = fields.ForeignKeyField(
        "models.Client",
        related_name=False,
        to_field="client_id",
        on_delete=fields.OnDelete.RESTRICT,
    )
    position = fields.IntField()
    input = fields.TextField()
    expected_decision = fields.CharField(max_length=32)
    rule = fields.TextField()
    failure_type = fields.CharField(max_length=32)
    context = fields.TextField(null=True)
    expected_numbers: fields.JSONField[list[str]] = fields.JSONField()
    owner = fields.CharField(max_length=32, null=True)
    unfixable_by_code = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "eval_goldens"
        unique_together = (("version", "position"),)

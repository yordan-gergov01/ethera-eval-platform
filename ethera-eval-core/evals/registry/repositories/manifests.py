"""Data access for Manifest versions: the current one and appending the next.

Role: `ManifestRepository` — `get_current_manifest` and `create_manifest` — on
  the caller's tenant-transaction connection.
Used by: `evals.registry.repositories` (re-export), and through it `evals.registry.services`.
Depends on: Tortoise (`IntegrityError`), `evals.registry.models.ManifestVersion`,
  `evals.registry.domain` (`Manifest`, `ModelBinding`), `evals.registry.repositories.records`,
  `common_lib.errors`, the `backend` barrel (`TransactionConnection`).
Key invariants: insert and read only — a version is never updated or deleted (INV-REG-07). Every
  query filters on `client_id` explicitly and runs under row security. A version number that is
  already taken (a concurrent replacement won) is a `MANIFEST_VERSION_CONFLICT`, never a 500:
  the unique (`product`, `version`) pair is what serialises concurrent writers (INV-REG-08).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from tortoise.exceptions import IntegrityError

from backend import TransactionConnection
from common_lib.errors import ConflictError, ErrorCode, NotFoundError
from evals.registry.domain import Manifest, ModelBinding
from evals.registry.models import ManifestVersion
from evals.registry.repositories.records import ManifestRecord, ProductRecord

VERSION_CONFLICT_MESSAGE = "The Manifest was changed meanwhile; reload it and try again."
FIELDS = (
    "version",
    "document",
    "bindings",
    "allowed_providers",
    "created_at",
    "created_by__username",
)


class ManifestRepository:
    """Manifest versions of Products the connection's tenant set admits."""

    async def get_current_manifest(
        self, connection: TransactionConnection, product: ProductRecord
    ) -> ManifestRecord:
        """The Product's highest version; a Product always has version 1."""
        rows = await (
            ManifestVersion.filter(product_id=product.id, client_id=product.client_id)
            .using_db(connection)
            .order_by("-version")
            .limit(1)
            .values(*FIELDS)
        )
        if not rows:
            raise NotFoundError(code=ErrorCode.PRODUCT_NOT_FOUND)
        return _record(product, rows[0])

    async def create_manifest(
        self,
        connection: TransactionConnection,
        product: ProductRecord,
        *,
        version: int,
        document: str,
        manifest: Manifest,
        created_by_id: UUID,
        created_by: str,
    ) -> ManifestRecord:
        """Append `version`; MANIFEST_VERSION_CONFLICT when that number is already taken."""
        try:
            row = await ManifestVersion.create(
                using_db=connection,
                product_id=product.id,
                client_id=product.client_id,
                version=version,
                document=document,
                bindings=[_binding_json(b) for b in manifest.bindings],
                allowed_providers=list(manifest.allowed_providers),
                created_by_id=created_by_id,
            )
        except IntegrityError as exc:
            raise ConflictError(
                VERSION_CONFLICT_MESSAGE, code=ErrorCode.MANIFEST_VERSION_CONFLICT
            ) from exc
        created_at: datetime = row.created_at
        return ManifestRecord(version, manifest, document, created_at, created_by)


def _binding_json(binding: ModelBinding) -> dict[str, str]:
    return {"role": binding.role, "provider": binding.provider, "model": binding.model}


def _record(product: ProductRecord, row: dict[str, Any]) -> ManifestRecord:  # Any: row values
    bindings: Sequence[dict[str, str]] = row["bindings"]
    manifest = Manifest(
        client_id=product.client_id,
        project_id=product.project_id,
        bindings=tuple(ModelBinding(**binding) for binding in bindings),
        allowed_providers=tuple(row["allowed_providers"]),
    )
    return ManifestRecord(
        version=row["version"],
        manifest=manifest,
        document=row["document"],
        created_at=row["created_at"],
        created_by=row["created_by__username"],
    )

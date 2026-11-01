"""Changing Manifests: creating a Product with version 1, and replacing the current version.

Role: `create_product` (the seed's and the test fixtures' path: a Product, its Manifest version
  1 and its `manifest_created` audit row) and `replace_manifest` (the use case behind
  `PUT /api/v1/products/{client_id}/{project_id}/manifest`).
Used by: `evals.registry.services` (re-export), and through it `evals.registry.api`, the seed
  (`evals.registry.services.seed`) and tests/integration/registry_fixtures.py.
Depends on: the `backend` barrel (`AuditEntry`, `CurrentUser`, `tenant_transaction`,
  `write_audit_row`), `evals.registry.domain`, `evals.registry.repositories`,
  `evals.registry.services.access`, `common_lib` (`AuditAction`, errors), structlog.
Key invariants: checks run in the contract's order (§2.3): not found (404), stale
  `base_version` (409), invalid Manifest (422), equal Manifest (200, nothing written), else a
  new version (201). A version and its audit row are written in ONE transaction, so both
  commit or neither does (INV-REG-03); refusals write nothing (§4). Audit details hold IDs,
  version numbers and section names only (INV-REG-11). Logs carry IDs and counts only — never
  document content, usernames or emails (§5, C-13): `manifest_replaced` per new version,
  `manifest_refused` with `problem_count` per invalid Manifest.
"""

from dataclasses import dataclass
from uuid import UUID

import structlog

from backend import AuditEntry, CurrentUser, tenant_transaction, write_audit_row
from common_lib.audit import AuditAction
from common_lib.errors import ConflictError, ErrorCode, FieldProblem, InvalidFieldsError
from evals.registry.domain import Manifest, ManifestProblem, changed_sections, check_manifest
from evals.registry.repositories import (
    ManifestRecord,
    ManifestRepository,
    ProductRecord,
    ProductRepository,
)
from evals.registry.services.access import member_client_ids_for, product_not_found

ENTITY_TYPE = "product"
VERSION_CONFLICT_MESSAGE = "The Manifest is no longer at this version; reload it and try again."

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ManifestReplacement:
    """The result of a replacement: the current version afterwards, and whether it is new."""

    manifest: ManifestRecord
    created: bool


def manifest_problems_error(problems: tuple[ManifestProblem, ...]) -> InvalidFieldsError:
    """MANIFEST_INVALID carrying every problem by field; messages never quote a value."""
    return InvalidFieldsError(
        [FieldProblem(p.field, p.type.value, p.message) for p in problems],
        code=ErrorCode.MANIFEST_INVALID,
    )


async def create_product(
    client_id: str, project_id: str, document: str, actor_id: UUID, actor_username: str
) -> ProductRecord:
    """Create the Product with Manifest version 1 unless it exists; never touch an existing one.

    `document` must be a valid Manifest for that Product (MANIFEST_INVALID otherwise).
    """
    checked = check_manifest(document, client_id, project_id)
    if not isinstance(checked, Manifest):
        raise manifest_problems_error(checked)
    products = ProductRepository()
    async with tenant_transaction([client_id]) as connection:
        existing = await products.get_product(connection, client_id, project_id)
        if existing is not None:
            return existing
        product = await products.create_product(connection, client_id, project_id)
        await ManifestRepository().create_manifest(
            connection,
            product,
            version=1,
            document=document,
            manifest=checked,
            created_by_id=actor_id,
            created_by=actor_username,
        )
        await write_audit_row(
            connection,
            AuditEntry(
                actor_id=actor_id,
                action=AuditAction.MANIFEST_CREATED,
                entity_type=ENTITY_TYPE,
                entity_id=product.id,
                details=_details(product, None, 1, ()),
            ),
        )
    return product


async def replace_manifest(
    actor: CurrentUser,
    client_id: str,
    project_id: str,
    *,
    base_version: int,
    document: str,
    client_ip: str | None,
) -> ManifestReplacement:
    """Replace the current Manifest, checked in the order of contract §2.3."""
    client_ids = await member_client_ids_for(actor.id, client_id, project_id)
    try:
        async with tenant_transaction(client_ids) as connection:
            product = await ProductRepository().get_product(connection, client_id, project_id)
            if product is None:
                raise product_not_found()
            manifests = ManifestRepository()
            current = await manifests.get_current_manifest(connection, product)
            if current.version != base_version:
                raise ConflictError(
                    VERSION_CONFLICT_MESSAGE, code=ErrorCode.MANIFEST_VERSION_CONFLICT
                )
            checked = check_manifest(document, client_id, project_id)
            if not isinstance(checked, Manifest):
                raise manifest_problems_error(checked)
            if checked == current.manifest:
                return ManifestReplacement(current, created=False)
            new = await manifests.create_manifest(
                connection,
                product,
                version=current.version + 1,
                document=document,
                manifest=checked,
                created_by_id=actor.id,
                created_by=actor.username,
            )
            sections = changed_sections(current.manifest, checked)
            await write_audit_row(
                connection,
                AuditEntry(
                    actor_id=actor.id,
                    action=AuditAction.MANIFEST_REPLACED,
                    entity_type=ENTITY_TYPE,
                    entity_id=product.id,
                    details=_details(product, current.version, new.version, sections),
                    client_ip=client_ip,
                ),
            )
    except InvalidFieldsError as exc:
        logger.info("manifest_refused", problem_count=len(exc.problems))
        raise
    logger.info(
        "manifest_replaced",
        product_id=str(product.id),
        client_id=client_id,
        from_version=current.version,
        to_version=new.version,
    )
    return ManifestReplacement(new, created=True)


def _details(
    product: ProductRecord, from_version: int | None, to_version: int, sections: tuple[str, ...]
) -> dict[str, UUID | str | int | list[str] | None]:
    return {
        "product_id": product.id,
        "client_id": product.client_id,
        "from_version": from_version,
        "to_version": to_version,
        "changed_sections": list(sections),
    }

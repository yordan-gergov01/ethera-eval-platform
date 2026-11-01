"""Reading Products: the caller's page of Products and one Product with its current Manifest.

Role: `list_products(user, limit, offset)` and `get_product(user, client_id, project_id)`, the
  read use cases behind `GET /api/v1/products` and `GET /api/v1/products/{client_id}/{project_id}`.
Used by: `evals.registry.services` (re-export), and through it `evals.registry.api`.
Depends on: the `backend` barrel (`CurrentUser`, `list_member_client_ids`,
  `tenant_transaction`), `evals.registry.repositories`, `evals.registry.services.access`.
Key invariants: the caller sees exactly the Products of the Clients they are a member of, for
  every role (PP-002); a user without memberships gets an empty page. Reads run in a tenant
  transaction, so row security holds even where a filter is forgotten (D-014).
"""

from dataclasses import dataclass

from backend import CurrentUser, list_member_client_ids, tenant_transaction
from evals.registry.repositories import (
    ManifestRecord,
    ManifestRepository,
    ProductPage,
    ProductRecord,
    ProductRepository,
)
from evals.registry.services.access import member_client_ids_for, product_not_found


@dataclass(frozen=True, slots=True)
class ProductDetails:
    """A Product and its current Manifest version."""

    product: ProductRecord
    manifest: ManifestRecord


async def list_products(user: CurrentUser, *, limit: int, offset: int) -> ProductPage:
    """One page of the caller's Products, ordered by `client_id`, then `project_id`."""
    client_ids = await list_member_client_ids(user.id)
    async with tenant_transaction(client_ids) as connection:
        return await ProductRepository().list_products(
            connection, client_ids, limit=limit, offset=offset
        )


async def get_product(user: CurrentUser, client_id: str, project_id: str) -> ProductDetails:
    """The Product with its current Manifest; PRODUCT_NOT_FOUND unless the caller may see it."""
    client_ids = await member_client_ids_for(user.id, client_id, project_id)
    async with tenant_transaction(client_ids) as connection:
        product = await ProductRepository().get_product(connection, client_id, project_id)
        if product is None:
            raise product_not_found()
        manifest = await ManifestRepository().get_current_manifest(connection, product)
    return ProductDetails(product, manifest)

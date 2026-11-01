"""Data access for Products: lookup, creation and the member-scoped page.

Role: `ProductRepository` — `get_product`, `create_product`, `list_products` — on the caller's
  tenant-transaction connection.
Used by: `evals.registry.repositories` (re-export), and through it `evals.registry.services`.
Depends on: Tortoise, `evals.registry.models.Product`, `evals.registry.domain.ModelBinding`,
  `evals.registry.repositories.records`, the `backend` barrel (`TransactionConnection`).
Key invariants: every query carries an explicit `client_id` filter AND runs under row security
  on the given connection, so either alone keeps other Clients' Products out (D-014). Listing is
  ordered by `client_id`, then `project_id` in byte (code-point) order, `COLLATE "C"`, never a
  locale collation (C-2). An offset beyond int8 is capped at `MAX_SQL_OFFSET`, so it reads an
  empty page with the real total (`test_list_offset_beyond_int64_answers_empty_page_not_500`).
  Records, never ORM objects, leave this module.
"""

import json
from collections.abc import Sequence
from typing import Any

from backend import TransactionConnection
from evals.registry.domain import ModelBinding
from evals.registry.models import Product
from evals.registry.repositories.records import ProductPage, ProductRecord, ProductSummary

# Raw SQL: the current version per Product (LATERAL ... LIMIT 1) with a byte-order sort is not
# expressible through the ORM's query builder. Bound parameters only.
LIST_PRODUCTS_SQL = """
SELECT p.client_id, p.project_id, m.version, m.bindings, m.created_at, u.username
FROM reg_products p
JOIN LATERAL (
    SELECT version, bindings, created_at, created_by_id
    FROM reg_manifests
    WHERE product_id = p.id AND client_id = p.client_id
    ORDER BY version DESC
    LIMIT 1
) m ON true
JOIN users u ON u.id = m.created_by_id
WHERE p.client_id = ANY($1::text[])
ORDER BY p.client_id COLLATE "C", p.project_id COLLATE "C"
LIMIT $2 OFFSET $3
"""
# The largest OFFSET PostgreSQL accepts (int8). The API admits any offset >= 0 (contract §2.1);
# a larger one is capped here, where it can only mean "past the end".
MAX_SQL_OFFSET = 2**63 - 1
COUNT_PRODUCTS_SQL = "SELECT count(*) AS total FROM reg_products WHERE client_id = ANY($1::text[])"


class ProductRepository:
    """Products of the Clients the connection's tenant set admits."""

    async def get_product(
        self, connection: TransactionConnection, client_id: str, project_id: str
    ) -> ProductRecord | None:
        """The Product, or None when it does not exist or is not visible."""
        product = (
            await Product.filter(client_id=client_id, project_id=project_id)
            .using_db(connection)
            .first()
        )
        if product is None:
            return None
        return ProductRecord(id=product.id, client_id=client_id, project_id=project_id)

    async def create_product(
        self, connection: TransactionConnection, client_id: str, project_id: str
    ) -> ProductRecord:
        """Insert a Product of the Client."""
        product = await Product.create(
            using_db=connection, client_id=client_id, project_id=project_id
        )
        return ProductRecord(id=product.id, client_id=client_id, project_id=project_id)

    async def list_products(
        self,
        connection: TransactionConnection,
        client_ids: Sequence[str],
        *,
        limit: int,
        offset: int,
    ) -> ProductPage:
        """One page of the Products of `client_ids`, byte-ordered, with the total."""
        client_ids = list(client_ids)
        rows = await connection.execute_query_dict(
            LIST_PRODUCTS_SQL, [client_ids, limit, min(offset, MAX_SQL_OFFSET)]
        )
        [count] = await connection.execute_query_dict(COUNT_PRODUCTS_SQL, [client_ids])
        return ProductPage(items=tuple(_summary(row) for row in rows), total=int(count["total"]))


def _summary(row: dict[str, Any]) -> ProductSummary:  # Any: database row values
    bindings = row["bindings"]
    if isinstance(bindings, str):
        bindings = json.loads(bindings)
    generation = next(b for b in bindings if b["role"] == "generation")
    return ProductSummary(
        client_id=row["client_id"],
        project_id=row["project_id"],
        manifest_version=row["version"],
        generation_binding=ModelBinding(**generation),
        changed_at=row["created_at"],
        changed_by=row["username"],
    )

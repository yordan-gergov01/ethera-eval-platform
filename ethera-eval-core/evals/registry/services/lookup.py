"""Looking up a Product on a connection another module already holds (R-201).

Role: `get_visible_product(connection, client_id, project_id)` — the Product the connection's
  tenant set may see, or the registry's PRODUCT_NOT_FOUND — for modules whose data belongs to a
  Product (the member path of their reads, their seeds, their test fixtures).
Used by: `evals.registry.services` (re-export), and through the `evals.registry` barrel
  `evals.evaluation.services`.
Depends on: `evals.registry.repositories` (`ProductRepository`), `evals.registry.services.access`
  (`product_not_found`), the `backend` barrel (`TransactionConnection`).
Key invariants: never opens a transaction: the caller opens ONE tenant transaction and passes
  its connection, so no nested transaction can replace the caller's Client set (research
  finding 3). On the member path the caller first runs `member_client_ids_for` to build that
  set, and a Product outside it is invisible under row security, so a missing Product, a
  non-member's Product and an off-pattern identifier all answer the one PRODUCT_NOT_FOUND
  (INV-REG-10).
"""

from backend import TransactionConnection
from evals.registry.repositories import ProductRecord, ProductRepository
from evals.registry.services.access import product_not_found


async def get_visible_product(
    connection: TransactionConnection, client_id: str, project_id: str
) -> ProductRecord:
    """The Product, when the connection may see it; PRODUCT_NOT_FOUND otherwise."""
    product = await ProductRepository().get_product(connection, client_id, project_id)
    if product is None:
        raise product_not_found()
    return product

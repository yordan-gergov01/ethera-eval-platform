"""Publishing Dataset versions: the one write path of Datasets and Goldens in this slice.

Role: `publish_dataset_version(client_id, project_id, goldens)` — the next version of a
  Product's Dataset (the Dataset is created at version 1 if it has none) — and
  `publish_on(connection, product, goldens)`, the same step on a transaction the caller holds
  (the seed's).
Used by: the seed (`evals.evaluation.services.seed`), which calls `publish_on` directly on its
  own transaction; `evals.evaluation.services` (re-export of `publish_dataset_version`), and
  through the `evals.evaluation` barrel tests/integration/evaluation_fixtures.py
  (`arrange_dataset_version`, contract §6), whose path follows the seed's steps
  (`tenant_transaction` → `get_visible_product` → `publish_on`).
Depends on: the `backend` barrel (`TransactionConnection`, `tenant_transaction`), the
  `evals.registry` barrel (`ProductRecord`, `get_visible_product`), `evals.evaluation.domain`
  (`Golden`), `evals.evaluation.repositories`, structlog.
Key invariants: a version and all its Goldens are written in ONE transaction, so a version is
  never seen half-written; numbers continue 1, 2, … without gaps (INV-EVAL-04); nothing is
  updated or deleted. Every Golden was validated on construction (PP-202, PP-205). There is no
  user writer in this slice (Fork D2 = A), so no audit row is written (C-213). The unique
  (Dataset, number) pair refuses a concurrent second writer of the same number. The log line
  carries IDs and counts only, never Golden content (FR-209).
"""

from collections.abc import Sequence

import structlog

from backend import TransactionConnection, tenant_transaction
from evals.evaluation.domain import Golden
from evals.evaluation.repositories import DatasetRepository, GoldenRepository
from evals.registry import ProductRecord, get_visible_product

logger = structlog.get_logger(__name__)


async def publish_on(
    connection: TransactionConnection, product: ProductRecord, goldens: Sequence[Golden]
) -> int:
    """Publish the next version of the Product's Dataset on `connection`; its number."""
    datasets = DatasetRepository()
    dataset = await datasets.get_dataset(connection, product.client_id, product.id)
    if dataset is None:
        dataset = await datasets.create_dataset(connection, product.client_id, product.id)
    versions = await datasets.list_versions(connection, dataset)
    number = 1 + max((version.number for version in versions), default=0)
    version_id = await datasets.create_version(connection, dataset, number)
    await GoldenRepository().create_goldens(connection, product.client_id, version_id, goldens)
    logger.info(
        "dataset_version_published",
        product_id=str(product.id),
        client_id=product.client_id,
        number=number,
        golden_count=len(goldens),
    )
    return number


async def publish_dataset_version(
    client_id: str, project_id: str, goldens: Sequence[Golden]
) -> int:
    """Publish the next version of the Product's Dataset; PRODUCT_NOT_FOUND without the Product."""
    async with tenant_transaction([client_id]) as connection:
        product = await get_visible_product(connection, client_id, project_id)
        return await publish_on(connection, product, goldens)

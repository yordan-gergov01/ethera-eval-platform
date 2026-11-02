"""The evaluation module's startup seed: the Dataset of the demo Product.

Role: `seed_demo_dataset` (the module's `ModuleMount.seed`): publishes version 1 of
  `acme / support-bot`'s Dataset with the Goldens of contract §3.5 unless the Dataset exists.
Used by: `evals.evaluation.module` (the mount).
Depends on: the `backend` barrel (`SeedContext`, `tenant_transaction`), the `evals.registry`
  barrel (`get_visible_product`), `evals.evaluation.repositories` (`DatasetRepository`),
  `evals.evaluation.services.publishing` (`publish_on`), `.demo_dataset`.
Key invariants: create-only and idempotent — runs at every start, after the registry's seed
  (MODULES order, each seed committed on its own, research finding 1), and never touches a
  Dataset that exists, whatever versions it has since gained (contract §3.1). The check and the
  publication run in one transaction; startups are serialised by the core's startup lock. No
  audit row (C-213).
"""

from backend import SeedContext, tenant_transaction
from evals.evaluation.repositories import DatasetRepository
from evals.evaluation.services.demo_dataset import DEMO_GOLDENS
from evals.evaluation.services.publishing import publish_on
from evals.registry import get_visible_product

DEMO_CLIENT_ID = "acme"
DEMO_PROJECT_ID = "support-bot"


async def seed_demo_dataset(_context: SeedContext) -> None:
    """Publish version 1 of the demo Product's Dataset unless the Dataset exists.

    The seed needs no actor: a Dataset version carries no publisher while only the seed
    publishes (Fork D2).
    """
    async with tenant_transaction([DEMO_CLIENT_ID]) as connection:
        product = await get_visible_product(connection, DEMO_CLIENT_ID, DEMO_PROJECT_ID)
        existing = await DatasetRepository().get_dataset(connection, product.client_id, product.id)
        if existing is None:
            await publish_on(connection, product, DEMO_GOLDENS)

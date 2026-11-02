"""Publishing Dataset versions: the gate before the write, and one Dataset per Product.

Role: pins evals.evaluation.services.publishing `publish_dataset_version` (the seed's path,
  contract §6) on refusals the sealed oracle does not reach: a Product that does not exist is the
  registry's PRODUCT_NOT_FOUND and writes nothing; a second Dataset for one Product is refused
  by the database (PP-208); and the seed's create-only check (`seed_demo_dataset`) publishes
  nothing when the demo Dataset exists.
Used by: pytest (integration; needs the test database and broker).
Depends on: `started_platform_app` (this folder's conftest.py); `backend_settings`,
  `connect_as_owner` from tests/integration/conftest.py; the `evals.evaluation` barrel and
  module services; the `evals.registry` barrel; the `backend` barrel.
Key invariants: counts are read as the owner, past row security, so "nothing written" cannot
  pass because a row was merely invisible.
"""

from uuid import UUID

import pytest
from httpx import AsyncClient
from tortoise.exceptions import IntegrityError

from backend import BackendSettings, SeedContext, tenant_transaction
from common_lib.errors import ErrorCode, NotFoundError
from evals.evaluation import publish_dataset_version
from evals.evaluation.domain import Decision, FailureType, Golden
from evals.evaluation.repositories import DatasetRepository
from evals.evaluation.services import seed_demo_dataset
from evals.registry import get_visible_product
from tests.integration.conftest import connect_as_owner

GOLDEN = Golden(
    input="A question",
    expected_decision=Decision.ESCALATE,
    rule="A rule",
    failure_type=FailureType.OUT_OF_DOCS,
)


async def _counts(settings: BackendSettings) -> tuple[int, int, int]:
    connection = await connect_as_owner(settings)
    try:
        return (
            await connection.fetchval("SELECT count(*) FROM eval_datasets"),
            await connection.fetchval("SELECT count(*) FROM eval_dataset_versions"),
            await connection.fetchval("SELECT count(*) FROM eval_goldens"),
        )
    finally:
        await connection.close()


@pytest.mark.usefixtures("started_platform_app")
async def test_publish_for_a_missing_product_is_product_not_found_and_writes_nothing(
    backend_settings: BackendSettings,
) -> None:
    before = await _counts(backend_settings)
    assert before == (1, 1, 19)  # anchor: the seed ran

    for client_id, project_id in (("acme", "no-such-bot"), ("no-such-client", "support-bot")):
        with pytest.raises(NotFoundError) as raised:
            await publish_dataset_version(client_id, project_id, [GOLDEN])
        assert raised.value.code == ErrorCode.PRODUCT_NOT_FOUND

    assert await _counts(backend_settings) == before


@pytest.mark.usefixtures("started_platform_app")
async def test_second_dataset_for_one_product_is_refused(
    backend_settings: BackendSettings,
) -> None:
    async with tenant_transaction(["acme"]) as connection:
        product = await get_visible_product(connection, "acme", "support-bot")

    with pytest.raises(IntegrityError):
        async with tenant_transaction(["acme"]) as connection:
            await DatasetRepository().create_dataset(connection, "acme", product.id)

    assert await _counts(backend_settings) == (1, 1, 19)


async def test_seed_publishes_nothing_when_the_dataset_exists(
    started_platform_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    before = await _counts(backend_settings)

    await seed_demo_dataset(SeedContext(UUID(int=0), "nobody"))

    assert before == await _counts(backend_settings) == (1, 1, 19)

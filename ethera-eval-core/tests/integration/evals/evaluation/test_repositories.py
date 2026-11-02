"""Evaluation data access under tenancy: every repository function is tenant-isolated.

Role: pins evals.evaluation.repositories `DatasetRepository` (`get_dataset`, `create_dataset`,
  `list_versions`, `create_version`) and `GoldenRepository` (`list_goldens`,
  `count_failure_types`, `create_goldens`) against the real PostgreSQL, as the runtime role: each
  function sees and writes only rows of the tenant transaction's Clients (spec FR-204, SC-201,
  D-014); all three tables have row security ENABLED and FORCED and are append-only for the
  runtime role (INV-EVAL-04).
Used by: pytest (integration; needs the test database and broker).
Depends on: `started_platform_app` (this folder's conftest.py), `arrange_*` from
  tests/integration/registry_fixtures.py, `arrange_dataset_version` from
  tests/integration/evaluation_fixtures.py; `backend_settings`, `connect_as_app`,
  `connect_as_owner` from tests/integration/conftest.py; the `backend` barrel.
Key invariants: Clients `acme` (seeded, 19 Goldens) and `globex` each hold a Product
  `support-bot` with a Dataset, so a leak cannot hide behind a missing name. Each read is proven
  twice: "row security alone" passes the OTHER Client's IDs to the explicit filter while the
  tenant set holds only one Client; "filter alone" admits BOTH Clients in the tenant set and
  names a record with the wrong Client, so only the explicit `client_id` filter keeps it out.
"""

from dataclasses import dataclass
from uuid import UUID

import asyncpg
import pytest
from httpx import AsyncClient
from tortoise.exceptions import OperationalError

from backend import BackendSettings, tenant_transaction
from evals.evaluation.domain import Decision, FailureType, Golden
from evals.evaluation.repositories import DatasetRecord, DatasetRepository, GoldenRepository
from tests.integration.conftest import connect_as_app, connect_as_owner
from tests.integration.evaluation_fixtures import arrange_dataset_version
from tests.integration.registry_fixtures import arrange_client, arrange_product, demo_document

TABLES = ("eval_datasets", "eval_dataset_versions", "eval_goldens")
GLOBEX_GOLDEN: dict[str, object] = {
    "input": "A globex question",
    "expected_decision": "escalate",
    "rule": "A globex rule",
    "failure_type": "out_of_docs",
    "context": None,
    "expected_numbers": [],
    "owner": None,
    "unfixable_by_code": False,
}
NEW_GOLDEN = Golden(
    input="An intruding question",
    expected_decision=Decision.ESCALATE,
    rule="An intruding rule",
    failure_type=FailureType.OUT_OF_DOCS,
)


@dataclass(frozen=True)
class World:
    acme_product: UUID
    globex_product: UUID
    portal_product: UUID  # globex's Product without a Dataset
    acme: DatasetRecord
    globex: DatasetRecord
    acme_version: UUID
    globex_version: UUID


async def _product_id(settings: BackendSettings, client_id: str, project_id: str) -> UUID:
    connection = await connect_as_owner(settings)
    try:
        product_id: UUID = await connection.fetchval(
            "SELECT id FROM reg_products WHERE client_id = $1 AND project_id = $2",
            client_id,
            project_id,
        )
    finally:
        await connection.close()
    return product_id


@pytest.fixture
async def world(started_platform_app: AsyncClient, backend_settings: BackendSettings) -> World:
    await arrange_client(backend_settings, "globex")
    for project_id in ("support-bot", "portal"):
        document = demo_document("globex", project_id)
        await arrange_product(backend_settings, "globex", project_id, document, "admin")
    assert (
        await arrange_dataset_version(backend_settings, "globex", "support-bot", [GLOBEX_GOLDEN])
        == 1
    )
    ids = {
        name: await _product_id(backend_settings, client_id, project_id)
        for name, client_id, project_id in (
            ("acme", "acme", "support-bot"),
            ("globex", "globex", "support-bot"),
            ("portal", "globex", "portal"),
        )
    }
    datasets = DatasetRepository()
    async with tenant_transaction(["acme", "globex"]) as connection:
        acme = await datasets.get_dataset(connection, "acme", ids["acme"])
        globex = await datasets.get_dataset(connection, "globex", ids["globex"])
        assert acme is not None
        assert globex is not None
        [acme_version] = await datasets.list_versions(connection, acme)
        [globex_version] = await datasets.list_versions(connection, globex)
    return World(
        ids["acme"], ids["globex"], ids["portal"], acme, globex, acme_version.id, globex_version.id
    )


async def test_get_dataset_only_within_the_tenant_set(world: World) -> None:
    datasets = DatasetRepository()
    async with tenant_transaction(["acme"]) as connection:
        own = await datasets.get_dataset(connection, "acme", world.acme_product)
        # Row security alone: the filter names globex, the tenant set does not.
        other = await datasets.get_dataset(connection, "globex", world.globex_product)
    async with tenant_transaction(["acme", "globex"]) as connection:
        # The filter alone: both Clients admitted, the Client named is not the Product's.
        crossed = await datasets.get_dataset(connection, "acme", world.globex_product)
    async with tenant_transaction([]) as connection:
        nothing = await datasets.get_dataset(connection, "acme", world.acme_product)

    assert own == world.acme
    assert (other, crossed, nothing) == (None, None, None)


async def test_list_versions_only_within_the_tenant_set(world: World) -> None:
    datasets = DatasetRepository()
    async with tenant_transaction(["acme"]) as connection:
        own = await datasets.list_versions(connection, world.acme)
        other = await datasets.list_versions(connection, world.globex)  # row security alone
    crossed_record = DatasetRecord(id=world.globex.id, client_id="acme")
    async with tenant_transaction(["acme", "globex"]) as connection:
        crossed = await datasets.list_versions(connection, crossed_record)  # the filter alone

    assert [(v.number, v.golden_count) for v in own] == [(1, 19)]
    assert (other, crossed) == ((), ())


async def test_list_goldens_only_within_the_tenant_set(world: World) -> None:
    goldens = GoldenRepository()
    async with tenant_transaction(["globex"]) as connection:
        own = await goldens.list_goldens(connection, "globex", world.globex_version)
        other = await goldens.list_goldens(connection, "acme", world.acme_version)  # row security
    async with tenant_transaction(["acme", "globex"]) as connection:
        crossed = await goldens.list_goldens(connection, "globex", world.acme_version)  # filter

    assert [(r.position, r.golden.input) for r in own] == [(1, "A globex question")]
    assert (other, crossed) == ((), ())


async def test_count_failure_types_only_within_the_tenant_set(world: World) -> None:
    goldens = GoldenRepository()
    async with tenant_transaction(["globex"]) as connection:
        own = await goldens.count_failure_types(connection, "globex", world.globex_version)
        other = await goldens.count_failure_types(connection, "acme", world.acme_version)
    async with tenant_transaction(["acme", "globex"]) as connection:
        crossed = await goldens.count_failure_types(connection, "globex", world.acme_version)

    assert own == {"out_of_docs": 1}
    assert (other, crossed) == ({}, {})


async def test_create_dataset_refused_outside_the_tenant_set(world: World) -> None:
    with pytest.raises(OperationalError, match="row-level security"):
        async with tenant_transaction(["acme"]) as connection:
            await DatasetRepository().create_dataset(connection, "globex", world.portal_product)

    async with tenant_transaction(["globex"]) as connection:
        assert (
            await DatasetRepository().get_dataset(connection, "globex", world.portal_product)
            is None
        )


async def test_create_version_refused_outside_the_tenant_set(world: World) -> None:
    with pytest.raises(OperationalError, match="row-level security"):
        async with tenant_transaction(["acme"]) as connection:
            await DatasetRepository().create_version(connection, world.globex, 2)

    async with tenant_transaction(["globex"]) as connection:
        assert len(await DatasetRepository().list_versions(connection, world.globex)) == 1


async def test_create_goldens_refused_outside_the_tenant_set(world: World) -> None:
    with pytest.raises(OperationalError, match="row-level security"):
        async with tenant_transaction(["acme"]) as connection:
            await GoldenRepository().create_goldens(
                connection, "globex", world.globex_version, [NEW_GOLDEN]
            )

    async with tenant_transaction(["globex"]) as connection:
        goldens = await GoldenRepository().list_goldens(connection, "globex", world.globex_version)
    assert len(goldens) == 1


async def test_raw_select_without_filter_sees_only_the_tenant_set(world: World) -> None:
    async with tenant_transaction(["globex"]) as connection:
        seen = {
            table: {
                row["client_id"]
                for row in await connection.execute_query_dict(f"SELECT client_id FROM {table}")  # noqa: S608 - fixed names
            }
            for table in TABLES
        }

    assert seen == {table: {"globex"} for table in TABLES}


@pytest.mark.usefixtures("started_platform_app")
async def test_evaluation_tables_force_row_security(backend_settings: BackendSettings) -> None:
    connection = await connect_as_owner(backend_settings)
    try:
        rows = await connection.fetch(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY($1::text[])",
            list(TABLES),
        )
    finally:
        await connection.close()

    assert {
        row["relname"]: (row["relrowsecurity"], row["relforcerowsecurity"]) for row in rows
    } == (dict.fromkeys(TABLES, (True, True)))


@pytest.mark.usefixtures("started_platform_app")
async def test_evaluation_tables_are_append_only_for_the_runtime_role(
    backend_settings: BackendSettings,
) -> None:
    connection = await connect_as_app(backend_settings)
    try:
        for table in TABLES:
            update, delete = f"UPDATE {table} SET created_at = now()", f"DELETE FROM {table}"  # noqa: S608 - fixed names
            for statement in (update, delete):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute(statement)
    finally:
        await connection.close()

"""Registry data access under tenancy: every repository function is tenant-isolated.

Role: pins evals.registry.repositories `ProductRepository` (`get_product`, `create_product`,
  `list_products`) and `ManifestRepository` (`get_current_manifest`, `create_manifest`) against the
  real PostgreSQL, as the runtime role: each function sees and writes only rows of the tenant
  transaction's Clients, and row security refuses other Clients' rows even when the explicit
  `client_id` filter names them (spec SC-002, D-014); the tables are append-only for the runtime
  role (INV-REG-07).
Used by: pytest (integration; needs the test database and broker).
Depends on: `started_platform_app`, `arrange_*` from tests/integration/registry_fixtures.py;
  `backend_settings`, `connect_as_app` from tests/integration/conftest.py; the `backend` barrel
  (`tenant_transaction`).
Key invariants: two Clients `acme` (seeded) and `globex` each hold a Product `support-bot`, so a
  leak cannot hide behind a missing name; "RLS alone" cases pass the OTHER Client's ID as the
  filter, so only row security stands between the caller and the row; the reverse,
  `test_explicit_client_filter_alone_excludes_other_clients`, admits both Clients in the tenant
  set, so only the explicit filter stands between them.
"""

from uuid import UUID

import asyncpg
import pytest
from httpx import AsyncClient
from tortoise.exceptions import OperationalError

from backend import BackendSettings, tenant_transaction
from common_lib.errors import ConflictError, ErrorCode, NotFoundError
from evals.registry.domain import Manifest, ModelBinding
from evals.registry.repositories import ManifestRepository, ProductRecord, ProductRepository
from tests.integration.conftest import connect_as_app
from tests.integration.registry_fixtures import (
    arrange_client,
    arrange_product,
    demo_document,
    product_entity_id,
)

MANIFEST = Manifest(
    "globex", "support-bot", (ModelBinding("generation", "mock", "mock-gen-large-v2"),), ("mock",)
)


async def _arrange_globex(settings: BackendSettings) -> None:
    await arrange_client(settings, "globex")
    await arrange_product(
        settings, "globex", "support-bot", demo_document("globex", "support-bot"), "admin"
    )


async def _admin_id(settings: BackendSettings) -> UUID:
    connection = await connect_as_app(settings)
    try:
        admin_id: UUID = await connection.fetchval("SELECT id FROM users WHERE username = 'admin'")
    finally:
        await connection.close()
    return admin_id


@pytest.fixture
async def two_clients(
    started_platform_app: AsyncClient, backend_settings: BackendSettings
) -> BackendSettings:
    await _arrange_globex(backend_settings)
    return backend_settings


async def test_get_product_only_within_the_tenant_set(two_clients: BackendSettings) -> None:
    products = ProductRepository()
    async with tenant_transaction(["acme"]) as connection:
        acme = await products.get_product(connection, "acme", "support-bot")
        # RLS alone: the filter names globex, the tenant set does not.
        globex = await products.get_product(connection, "globex", "support-bot")
    async with tenant_transaction([]) as connection:
        nothing = await products.get_product(connection, "acme", "support-bot")

    assert acme is not None
    assert acme.client_id == "acme"
    assert globex is None
    assert nothing is None


async def test_list_products_only_within_the_tenant_set(two_clients: BackendSettings) -> None:
    products = ProductRepository()
    async with tenant_transaction(["acme"]) as connection:
        own = await products.list_products(connection, ["acme"], limit=50, offset=0)
        # RLS alone: the explicit filter asks for both Clients.
        widened = await products.list_products(connection, ["acme", "globex"], limit=50, offset=0)
    async with tenant_transaction(["acme", "globex"]) as connection:
        both = await products.list_products(connection, ["acme", "globex"], limit=50, offset=0)

    assert [(i.client_id, i.project_id) for i in own.items] == [("acme", "support-bot")]
    assert (own.total, widened.total) == (1, 1)
    assert [i.client_id for i in widened.items] == ["acme"]
    assert [i.client_id for i in both.items] == ["acme", "globex"]
    assert both.total == 2


async def test_explicit_client_filter_alone_excludes_other_clients(
    two_clients: BackendSettings,
) -> None:
    # The tenant set admits both Clients, so only the explicit `client_id` filter can keep
    # the other Client's rows out (D-014: either alone suffices).
    await arrange_product(
        two_clients, "globex", "globex-only", demo_document("globex", "globex-only"), "admin"
    )
    products = ProductRepository()
    async with tenant_transaction(["acme", "globex"]) as connection:
        page = await products.list_products(connection, ["acme"], limit=50, offset=0)
        acme = await products.get_product(connection, "acme", "support-bot")
        globex = await products.get_product(connection, "globex", "support-bot")
        missing = await products.get_product(connection, "acme", "globex-only")

    assert [(i.client_id, i.project_id) for i in page.items] == [("acme", "support-bot")]
    assert page.total == 1
    assert acme is not None
    assert globex is not None
    assert str(acme.id) == await product_entity_id(two_clients, "acme", "support-bot")
    assert str(globex.id) == await product_entity_id(two_clients, "globex", "support-bot")
    assert missing is None


async def test_raw_select_without_filter_sees_only_the_tenant_set(
    two_clients: BackendSettings,
) -> None:
    async with tenant_transaction(["globex"]) as connection:
        products = await connection.execute_query_dict("SELECT client_id FROM reg_products")
        manifests = await connection.execute_query_dict("SELECT client_id FROM reg_manifests")

    assert {row["client_id"] for row in products} == {"globex"}
    assert {row["client_id"] for row in manifests} == {"globex"}


async def test_create_product_refused_outside_the_tenant_set(two_clients: BackendSettings) -> None:
    with pytest.raises(OperationalError, match="row-level security"):
        async with tenant_transaction(["acme"]) as connection:
            await ProductRepository().create_product(connection, "globex", "intruder")

    async with tenant_transaction(["globex"]) as connection:
        assert await ProductRepository().get_product(connection, "globex", "intruder") is None


async def test_get_current_manifest_only_within_the_tenant_set(
    two_clients: BackendSettings,
) -> None:
    async with tenant_transaction(["globex"]) as connection:
        globex = await ProductRepository().get_product(connection, "globex", "support-bot")
    assert globex is not None

    async with tenant_transaction(["globex"]) as connection:
        current = await ManifestRepository().get_current_manifest(connection, globex)
    assert (current.version, current.created_by) == (1, "admin")

    # RLS alone: the record names globex, the tenant set is acme.
    with pytest.raises(NotFoundError):
        async with tenant_transaction(["acme"]) as connection:
            await ManifestRepository().get_current_manifest(connection, globex)


async def test_create_manifest_refused_outside_the_tenant_set(two_clients: BackendSettings) -> None:
    admin_id = await _admin_id(two_clients)
    async with tenant_transaction(["globex"]) as connection:
        globex = await ProductRepository().get_product(connection, "globex", "support-bot")
    assert globex is not None

    with pytest.raises(OperationalError, match="row-level security"):
        async with tenant_transaction(["acme"]) as connection:
            await ManifestRepository().create_manifest(
                connection,
                globex,
                version=2,
                document="x",
                manifest=MANIFEST,
                created_by_id=admin_id,
                created_by="admin",
            )

    async with tenant_transaction(["globex"]) as connection:
        assert (await ManifestRepository().get_current_manifest(connection, globex)).version == 1


async def test_create_manifest_taken_version_is_a_version_conflict(
    two_clients: BackendSettings,
) -> None:
    admin_id = await _admin_id(two_clients)
    async with tenant_transaction(["globex"]) as connection:
        globex = await ProductRepository().get_product(connection, "globex", "support-bot")
    assert isinstance(globex, ProductRecord)

    with pytest.raises(ConflictError) as raised:
        async with tenant_transaction(["globex"]) as connection:
            await ManifestRepository().create_manifest(
                connection,
                globex,
                version=1,
                document="x",
                manifest=MANIFEST,
                created_by_id=admin_id,
                created_by="admin",
            )

    assert raised.value.code == ErrorCode.MANIFEST_VERSION_CONFLICT


@pytest.mark.usefixtures("started_platform_app")
async def test_registry_tables_are_append_only_for_the_runtime_role(
    backend_settings: BackendSettings,
) -> None:
    connection = await connect_as_app(backend_settings)
    try:
        for table in ("reg_products", "reg_manifests"):
            update, delete = f"UPDATE {table} SET created_at = now()", f"DELETE FROM {table}"  # noqa: S608 - fixed names
            for statement in (update, delete):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await connection.execute(statement)
    finally:
        await connection.close()

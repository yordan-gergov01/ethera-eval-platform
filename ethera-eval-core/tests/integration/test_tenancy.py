"""Row security through the tenant transaction, on the real runtime pool.

Role: pins backend.dal.tenancy `tenant_transaction` against a scratch client-owned table with
  RLS ENABLE + FORCE and the policy shape client-owned tables use
  (`client_id = ANY (app_current_tenants())`, migration 0004): the listed Clients' rows only;
  an empty set and an unset setting admit no row and never raise; the setting never leaks to
  the next borrower of a pooled connection, after commit or rollback, and is transaction-local
  even on the same connection (the pool's own reset is not what keeps it from leaking).
Used by: pytest (integration — needs the test database).
Depends on: `backend_settings`, `connect_as_owner` from tests/integration/conftest.py; the core
  app (`backend.main.create_app`) for its runtime pool; Tortoise's `connections`.
Key invariants: the scratch table is created by the migration owner, as module tables are;
  every read goes through the runtime role, which has no BYPASSRLS; the leak tests use a pool of
  one connection, so the next borrower is the same physical connection.
"""

from collections.abc import AsyncIterator

import pytest
from tortoise import connections

from backend.core.settings import BackendSettings
from backend.dal.tenancy import TENANTS_SETTING, tenant_transaction
from backend.main import create_app
from tests.integration.conftest import connect_as_owner


@pytest.fixture
async def single_connection_app(backend_settings: BackendSettings) -> AsyncIterator[None]:
    """The core app started on a runtime pool of ONE connection, with a scratch RLS table."""
    settings = backend_settings.model_copy(update={"db_pool_max_size": 1})
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        owner = await connect_as_owner(settings)
        try:
            await owner.execute(
                "CREATE TABLE it_scratch_owned (id serial PRIMARY KEY, client_id text NOT NULL)"
            )
            await owner.execute("ALTER TABLE it_scratch_owned ENABLE ROW LEVEL SECURITY")
            await owner.execute("ALTER TABLE it_scratch_owned FORCE ROW LEVEL SECURITY")
            await owner.execute(
                "CREATE POLICY tenant ON it_scratch_owned "
                "USING (client_id = ANY (app_current_tenants())) "
                "WITH CHECK (client_id = ANY (app_current_tenants()))"
            )
            await owner.execute(f"GRANT SELECT, INSERT ON it_scratch_owned TO {settings.db_user}")
            await owner.execute(
                f"GRANT USAGE ON SEQUENCE it_scratch_owned_id_seq TO {settings.db_user}"
            )
            await owner.execute(
                "INSERT INTO it_scratch_owned (client_id) VALUES ('acme'), ('acme'), ('beta')"
            )
        finally:
            await owner.close()
        yield


async def _visible_in(client_ids: list[str]) -> list[str]:
    async with tenant_transaction(client_ids) as connection:
        rows = await connection.execute_query_dict(
            "SELECT client_id FROM it_scratch_owned ORDER BY client_id"
        )
    return [row["client_id"] for row in rows]


async def _setting_on_the_pool() -> tuple[object, object]:
    rows = await connections.get("default").execute_query_dict(
        "SELECT current_setting($1, true) AS value, app_current_tenants() AS tenants",
        [TENANTS_SETTING],
    )
    return rows[0]["value"], rows[0]["tenants"]


@pytest.mark.usefixtures("single_connection_app")
async def test_tenant_transaction_admits_only_the_listed_clients() -> None:
    assert await _visible_in(["acme"]) == ["acme", "acme"]
    assert await _visible_in(["beta"]) == ["beta"]
    assert await _visible_in(["acme", "beta"]) == ["acme", "acme", "beta"]


@pytest.mark.usefixtures("single_connection_app")
async def test_tenant_transaction_empty_set_admits_no_row() -> None:
    assert await _visible_in([]) == []


@pytest.mark.usefixtures("single_connection_app")
async def test_unset_setting_admits_no_row_and_never_raises() -> None:
    rows = await connections.get("default").execute_query_dict("SELECT * FROM it_scratch_owned")

    assert rows == []


@pytest.mark.usefixtures("single_connection_app")
async def test_tenant_transaction_cannot_insert_for_another_client() -> None:
    with pytest.raises(Exception, match="row-level security"):
        async with tenant_transaction(["acme"]) as connection:
            await connection.execute_query(
                "INSERT INTO it_scratch_owned (client_id) VALUES ('beta')"
            )

    assert await _visible_in(["beta"]) == ["beta"]


@pytest.mark.usefixtures("single_connection_app")
async def test_setting_does_not_leak_to_the_next_borrower_after_commit() -> None:
    assert await _visible_in(["acme"]) == ["acme", "acme"]

    value, tenants = await _setting_on_the_pool()

    assert value in ("", None)
    assert tenants == []


@pytest.mark.usefixtures("single_connection_app")
async def test_setting_does_not_leak_to_the_next_borrower_after_rollback() -> None:
    class RolledBackError(Exception):
        pass

    with pytest.raises(RolledBackError):
        async with tenant_transaction(["acme"]):
            raise RolledBackError

    value, tenants = await _setting_on_the_pool()

    assert value in ("", None)
    assert tenants == []


@pytest.mark.usefixtures("single_connection_app")
async def test_setting_is_transaction_local_not_session_wide() -> None:
    # The pool's reset on release would hide a session-wide value from the next borrower,
    # so the scope is checked on the SAME connection: end the transaction by hand, then
    # read the setting before the helper's own COMMIT (a no-op warning) releases it.
    async with tenant_transaction(["acme"]) as connection:
        await connection.execute_query("COMMIT")
        rows = await connection.execute_query_dict(
            "SELECT current_setting($1, true) AS value", [TENANTS_SETTING]
        )
        await connection.execute_query("BEGIN")

    assert rows[0]["value"] in ("", None)

"""The two database roles at startup: asserted, granted, and kept apart.

Role: pins backend.core.startup `prepare_database` / `assert_database_roles` /
  `grant_runtime_access` against the real PostgreSQL: startup fails fast, before any migration,
  when the runtime role has BYPASSRLS; the runtime role gets data access but no DDL, no access
  to the migration ledger, and INSERT + SELECT only on the audit table and on every table a
  module declares append-only (`ModuleMount.append_only_tables`); requests run as the
  runtime role, never as the owner (D-014, D-021, D-022 Fork R2 = A).
Used by: pytest (integration — needs the test database).
Depends on: `fresh_database`, `backend_settings`, `started_app`, `connect_as_app`,
  `connect_as_owner`, `SERVER` from tests/integration/conftest.py; Tortoise's `connections`.
Key invariants: roles are cluster-wide, so a role created here has a unique name and is always
  dropped; every privilege is checked both by catalog (`has_table_privilege`) and by an actual
  statement that must be refused.
"""

from collections.abc import AsyncIterator
from uuid import uuid4

import asyncpg
import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from tortoise import connections

from backend.core.modules import ModuleMount
from backend.core.settings import BackendSettings, DatabaseSettings
from backend.core.startup import DatabaseRoleError, prepare_database
from tests.integration.conftest import SERVER, connect_as_app, connect_as_owner

ROLE_PASSWORD = "test-only-not-a-secret"


async def _no_seed() -> None:
    return None


@pytest.fixture
async def bypassing_role() -> AsyncIterator[str]:
    """A throw-away LOGIN role WITH BYPASSRLS, dropped afterwards."""
    name = f"it_bypass_{uuid4().hex[:10]}"
    admin = await SERVER.connect_as_superuser(SERVER.maintenance_db)
    try:
        await admin.execute(f"CREATE ROLE {name} LOGIN BYPASSRLS PASSWORD '{ROLE_PASSWORD}'")
        yield name
    finally:
        await admin.execute(f"DROP ROLE IF EXISTS {name}")
        await admin.close()


async def test_startup_fails_fast_when_the_runtime_role_bypasses_row_security(
    fresh_database: DatabaseSettings, bypassing_role: str
) -> None:
    settings = fresh_database.model_copy(
        update={"db_user": bypassing_role, "db_password": SecretStr(ROLE_PASSWORD)}
    )

    with pytest.raises(DatabaseRoleError, match="runtime role must not have BYPASSRLS"):
        await prepare_database(settings, (), seed_core=_no_seed, admin_username="admin")

    owner = await connect_as_owner(fresh_database)
    try:
        ledger = await owner.fetchval("SELECT to_regclass('tortoise_migrations')")
    finally:
        await owner.close()
    assert ledger is None  # nothing was migrated


async def test_startup_fails_fast_when_the_owner_role_is_missing(
    fresh_database: DatabaseSettings,
) -> None:
    # The lock connection itself is the owner's, so a missing owner cannot even connect.
    settings = fresh_database.model_copy(update={"db_owner_user": f"it_none_{uuid4().hex[:8]}"})

    with pytest.raises(asyncpg.InvalidAuthorizationSpecificationError):
        await prepare_database(settings, (), seed_core=_no_seed, admin_username="admin")


async def test_requests_run_as_the_runtime_role(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    rows = await connections.get("default").execute_query_dict("SELECT current_user AS role")

    assert rows == [{"role": backend_settings.db_user}]


async def _privileges(settings: DatabaseSettings, table: str) -> dict[str, bool]:
    connection = await connect_as_app(settings)
    try:
        return {
            privilege: await connection.fetchval(
                "SELECT has_table_privilege(current_user, $1, $2)", table, privilege
            )
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
        }
    finally:
        await connection.close()


@pytest.mark.usefixtures("started_app")
async def test_runtime_role_has_data_access_without_truncate(
    backend_settings: BackendSettings,
) -> None:
    for table in ("users", "clients", "client_memberships", "rate_limit_counters"):
        assert await _privileges(backend_settings, table) == {
            "SELECT": True,
            "INSERT": True,
            "UPDATE": True,
            "DELETE": True,
            "TRUNCATE": False,
        }, table


@pytest.mark.usefixtures("started_app")
async def test_runtime_role_may_only_insert_and_read_audit_rows(
    backend_settings: BackendSettings,
) -> None:
    assert await _privileges(backend_settings, "audit_rows") == {
        "SELECT": True,
        "INSERT": True,
        "UPDATE": False,
        "DELETE": False,
        "TRUNCATE": False,
    }
    connection = await connect_as_app(backend_settings)
    try:
        assert await connection.fetchval("SELECT count(*) FROM audit_rows") == 0
        for statement in (
            "UPDATE audit_rows SET action = 'x'",
            "DELETE FROM audit_rows",
            "TRUNCATE audit_rows",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(statement)
    finally:
        await connection.close()


@pytest.mark.usefixtures("started_app")
async def test_runtime_role_cannot_touch_the_migration_ledger_or_run_ddl(
    backend_settings: BackendSettings,
) -> None:
    connection = await connect_as_app(backend_settings)
    try:
        for statement in (
            "SELECT * FROM tortoise_migrations",
            "CREATE TABLE it_forbidden (id int)",
            "ALTER TABLE users ADD COLUMN it_forbidden int",
            "DROP TABLE audit_rows",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(statement)
    finally:
        await connection.close()


async def test_a_second_startup_keeps_the_grants(fresh_database: DatabaseSettings) -> None:
    await prepare_database(fresh_database, (), seed_core=_no_seed, admin_username="admin")
    await prepare_database(fresh_database, (), seed_core=_no_seed, admin_username="admin")

    assert (await _privileges(fresh_database, "audit_rows"))["UPDATE"] is False
    assert (await _privileges(fresh_database, "users"))["UPDATE"] is True


async def test_module_append_only_table_is_insert_and_select_only(
    fresh_database: DatabaseSettings,
) -> None:
    owner = await connect_as_owner(fresh_database)
    try:
        await owner.execute("CREATE TABLE it_module_log (id int)")
    finally:
        await owner.close()
    probe = ModuleMount(name="probe", append_only_tables=("it_module_log",))

    await prepare_database(fresh_database, (probe,), seed_core=_no_seed, admin_username="admin")

    assert await _privileges(fresh_database, "it_module_log") == {
        "SELECT": True,
        "INSERT": True,
        "UPDATE": False,
        "DELETE": False,
        "TRUNCATE": False,
    }
    connection = await connect_as_app(fresh_database)
    try:
        await connection.execute("INSERT INTO it_module_log VALUES (1)")
        for statement in ("UPDATE it_module_log SET id = 2", "DELETE FROM it_module_log"):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(statement)
    finally:
        await connection.close()

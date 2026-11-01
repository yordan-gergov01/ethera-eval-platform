"""Migrations at startup: the expected schema, applied exactly once across replicas.

Role: pins backend.core.startup `apply_migrations` under `startup_lock` and the schema the
  migrations/ package produces: exactly the expected indexes, unlogged rate-limit counters,
  pgvector present after startup, the migration owner owning every table while the runtime role
  owns nothing, neither with superuser rights (D-021), and the tenant-set function.
Used by: pytest (integration — needs the test database).
Depends on: `fresh_database` from tests/integration/conftest.py, whose superuser has already
  created the vector extension, as in production; the migration files in migrations/.
Key invariants: concurrent startups are serialised by the advisory lock and apply each
  migration exactly once; a second startup changes nothing; the expected index set is exact,
  so an unplanned index fails the test.
"""

import asyncio
from pathlib import Path

import asyncpg

from backend.core.settings import DatabaseSettings
from backend.core.startup import apply_migrations, startup_lock
from tests.integration.conftest import connect_as_owner


async def run_startup_tasks(settings: DatabaseSettings) -> None:
    """What every replica does at startup before seeding: migrate under the lock."""
    async with startup_lock(settings):
        await apply_migrations(settings)


MIGRATION_FILES = sorted(
    path.stem for path in (Path(__file__).parents[2] / "migrations").glob("[0-9]*.py")
)

# Every index the schema needs today, and nothing more.
EXPECTED_INDEXES = {
    ("permissions", "permissions_pkey", "(id)"),
    ("permissions", "permissions_code_key", "(code)"),
    ("roles", "roles_pkey", "(id)"),
    ("roles", "roles_name_key", "(name)"),
    ("users", "users_pkey", "(id)"),
    ("users", "users_username_key", "(username)"),
    ("users", "users_email_key", "(email)"),
    ("role_permissions", "uidx_role_permis_role_id_6a25fe", "(role_id, permission_id)"),
    ("rate_limit_counters", "rate_limit_counters_pkey", "(key, window_start)"),
    ("clients", "clients_pkey", "(id)"),
    ("clients", "clients_client_id_key", "(client_id)"),
    ("client_memberships", "client_memberships_pkey", "(id)"),
    ("client_memberships", "uid_client_memb_user_id_59cbb3", "(user_id, client_id)"),
    ("audit_rows", "audit_rows_pkey", "(id)"),
}
# The application creates no non-unique index yet.
NON_UNIQUE_INDEXES: set[str] = set()


async def _connect(settings: DatabaseSettings) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        database=settings.db_name,
    )


async def _applied_migrations(settings: DatabaseSettings) -> list[asyncpg.Record]:
    # The migration ledger is the owner's: the runtime role has no grant on it.
    connection = await connect_as_owner(settings)
    try:
        return await connection.fetch(
            "SELECT name, applied_at FROM tortoise_migrations ORDER BY id"
        )
    finally:
        await connection.close()


async def test_migrations_create_exactly_the_expected_indexes(
    fresh_database: DatabaseSettings,
) -> None:
    await run_startup_tasks(fresh_database)

    connection = await _connect(fresh_database)
    try:
        rows = await connection.fetch(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename <> 'tortoise_migrations'"
        )
    finally:
        await connection.close()

    indexes = {
        (row["tablename"], row["indexname"], row["indexdef"].split(" USING btree ")[1])
        for row in rows
    }
    assert indexes == EXPECTED_INDEXES
    assert all(
        row["indexdef"].startswith("CREATE UNIQUE INDEX")
        for row in rows
        if row["indexname"] not in NON_UNIQUE_INDEXES
    )


async def test_rate_limit_counters_are_unlogged(fresh_database: DatabaseSettings) -> None:
    await run_startup_tasks(fresh_database)

    connection = await _connect(fresh_database)
    try:
        persistence = await connection.fetchval(
            "SELECT relpersistence FROM pg_class WHERE relname = 'rate_limit_counters'"
        )
    finally:
        await connection.close()
    # "char" column: asyncpg returns it as bytes.
    assert persistence == b"u"


async def test_pgvector_is_enabled(fresh_database: DatabaseSettings) -> None:
    await run_startup_tasks(fresh_database)

    connection = await _connect(fresh_database)
    try:
        extension = await connection.fetchval(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        )
    finally:
        await connection.close()

    assert extension == "vector"


async def test_concurrent_startups_apply_each_migration_exactly_once(
    fresh_database: DatabaseSettings,
) -> None:
    # Two replicas starting at the same moment: the advisory lock serialises them.
    await asyncio.gather(run_startup_tasks(fresh_database), run_startup_tasks(fresh_database))

    applied = await _applied_migrations(fresh_database)
    assert [row["name"] for row in applied] == MIGRATION_FILES


async def test_a_second_startup_changes_nothing(fresh_database: DatabaseSettings) -> None:
    await run_startup_tasks(fresh_database)
    before = await _applied_migrations(fresh_database)

    await run_startup_tasks(fresh_database)

    assert await _applied_migrations(fresh_database) == before


async def test_migration_owner_owns_the_schema_and_the_runtime_role_owns_nothing(
    fresh_database: DatabaseSettings,
) -> None:
    # Rewritten for two roles (D-021): it replaces the template's single-role pin
    # `test_application_role_owns_the_schema_without_superuser_rights`.
    await run_startup_tasks(fresh_database)

    connection = await _connect(fresh_database)
    try:
        roles = await connection.fetch(
            "SELECT rolname, rolsuper FROM pg_roles WHERE rolname = ANY($1::text[])",
            [fresh_database.db_user, fresh_database.db_owner_user],
        )
        owners = await connection.fetch(
            "SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'"
        )
        runtime_owns = await connection.fetchval(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relowner = "
            "(SELECT oid FROM pg_roles WHERE rolname = current_user)"
        )
        schema_owner = await connection.fetchval(
            "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'public'"
        )
    finally:
        await connection.close()

    assert {row["rolname"]: row["rolsuper"] for row in roles} == {
        fresh_database.db_user: False,
        fresh_database.db_owner_user: False,
    }
    assert [row["tableowner"] for row in owners] == [fresh_database.db_owner_user]
    assert runtime_owns == 0
    # PostgreSQL 15+: the public schema belongs to the database owner, the migration owner.
    assert schema_owner == "pg_database_owner"


async def test_tenant_set_function_is_empty_when_unset_or_cleared(
    fresh_database: DatabaseSettings,
) -> None:
    await run_startup_tasks(fresh_database)

    connection = await _connect(fresh_database)
    try:
        unset = await connection.fetchval("SELECT app_current_tenants()")
        async with connection.transaction():
            await connection.execute("SELECT set_config('app.current_tenants', 'b,a', true)")
            inside = await connection.fetchval("SELECT app_current_tenants()")
        cleared = await connection.fetchval("SELECT app_current_tenants()")
    finally:
        await connection.close()

    assert unset == []
    assert inside == ["b", "a"]
    assert cleared == []

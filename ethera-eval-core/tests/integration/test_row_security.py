"""Mechanical guard: every client-owned table has row security ENABLED and FORCED.

Role: after the full platform app (core + every mounted module, `evals.app.create_app`) has
  migrated a fresh database, every table in `public` with a `client_id` column — except the core
  identity tables `clients` and `client_memberships` — must have RLS enabled and forced (D-014,
  .claude/rules/database.md). Slice 001 wave 1 has no client-owned table yet, so the guard
  passes on an empty set until the registry's tables arrive; the negative case proves it fires.
Used by: pytest (integration — needs the test database).
Depends on: `backend_settings`, `connect_as_owner` from tests/integration/conftest.py;
  `evals.app.create_app`.
Key invariants: the identity tables are exempt by name and with a reason (memberships are
  read before any tenant is set, D-022 Fork R1 = A); any other table carrying `client_id` is
  client-owned by definition.
"""

import asyncpg

from backend.core.settings import BackendSettings
from evals.app import create_app
from tests.integration.conftest import connect_as_owner

# Core identity data, guarded by Permissions instead of row security (D-022 Fork R1 = A).
IDENTITY_TABLES = frozenset({"clients", "client_memberships"})


async def unforced_client_owned_tables(connection: asyncpg.Connection) -> list[str]:
    """Client-owned tables (a `client_id` column) without RLS enabled AND forced."""
    rows = await connection.fetch(
        "SELECT c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'client_id' "
        "AND NOT a.attisdropped "
        "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
        "AND NOT (c.relrowsecurity AND c.relforcerowsecurity) "
        "ORDER BY c.relname"
    )
    return [row["relname"] for row in rows if row["relname"] not in IDENTITY_TABLES]


async def test_every_client_owned_table_forces_row_security(
    backend_settings: BackendSettings,
) -> None:
    app = create_app(backend_settings)
    async with app.router.lifespan_context(app):
        connection = await connect_as_owner(backend_settings)
        try:
            assert await unforced_client_owned_tables(connection) == []
        finally:
            await connection.close()


async def test_guard_fires_on_a_client_owned_table_without_forced_row_security(
    backend_settings: BackendSettings,
) -> None:
    app = create_app(backend_settings)
    async with app.router.lifespan_context(app):
        connection = await connect_as_owner(backend_settings)
        try:
            await connection.execute("CREATE TABLE it_unforced (client_id text NOT NULL)")
            await connection.execute("CREATE TABLE it_enabled_only (client_id text NOT NULL)")
            await connection.execute("ALTER TABLE it_enabled_only ENABLE ROW LEVEL SECURITY")
            await connection.execute("CREATE TABLE it_forced (client_id text NOT NULL)")
            await connection.execute("ALTER TABLE it_forced ENABLE ROW LEVEL SECURITY")
            await connection.execute("ALTER TABLE it_forced FORCE ROW LEVEL SECURITY")

            assert await unforced_client_owned_tables(connection) == [
                "it_enabled_only",
                "it_unforced",
            ]
        finally:
            await connection.close()

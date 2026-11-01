"""The work every replica does once at startup, on the migration owner's connections.

Role: `prepare_database` runs the whole startup sequence under the cluster-wide advisory lock
  (`startup_lock`): assert the two roles' attributes (`assert_database_roles`), apply the
  migrations (`apply_migrations`), grant the runtime role its data access
  (`grant_runtime_access`), then seed — the core's admin seed, then every module's `seed` — on a
  short-lived owner ORM context that is closed before the runtime pool opens.
Used by: `backend.main` (the lifespan); tests/integration/test_migrations.py,
  tests/integration/test_database_roles.py, tests/integration/test_module_seeds.py,
  tests/unit/backend/test_startup.py.
Depends on: asyncpg (a dedicated owner connection for the lock, the assertions and the grants),
  Tortoise's built-in migrations, `backend.core.database` (`tortoise_config`),
  `backend.core.modules` (`ModuleMount`, `SeedContext`), `backend.core.settings`.
Key invariants: every replica runs the startup tasks, but the advisory lock serialises them —
  the first replica does the work, the others wait and find nothing left to do (template_core
  D-004). The lock lives on its own connection and is released if that connection drops, so a
  crashed replica never leaves it locked; `lock_timeout` makes startup fail instead of waiting
  forever. Startup FAILS FAST, before any migration, unless the migration owner has BYPASSRLS
  and the runtime role has neither BYPASSRLS nor superuser rights nor membership of the owner
  (D-014, D-021). Everything here connects as the owner; requests never do: the owner ORM
  context is opened without the global fallback and always closed, so it cannot leak into the
  runtime pool (D-022 Fork R2 = A). Grants are re-applied at every start because a migration
  cannot know the runtime role's name: data access on every table except the migration
  ledger, and INSERT + SELECT only on the append-only tables — the core's own and those each
  module declares (`ModuleMount.append_only_tables`). Module migrations are applied
  with the core's in one graph (D-007).
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

import asyncpg
import structlog
from tortoise import Tortoise
from tortoise.migrations.api import migrate

from backend.core.database import ModuleModels, tortoise_config
from backend.core.modules import ModuleMount, SeedContext
from backend.core.settings import DatabaseSettings

# Identifies "ethera-eval-core startup tasks" among PostgreSQL advisory locks. Not a secret:
# any number works as long as every replica uses the same one, which is why it is a
# constant in code rather than a setting that could differ between hosts.
STARTUP_LOCK_ID = 7_420_150_268_313_725_001
# Fail startup instead of waiting forever if another replica holds the lock too long.
LOCK_TIMEOUT = "120s"
# Tortoise's migration ledger: the runtime role never reads or writes it.
MIGRATIONS_TABLE = "tortoise_migrations"
# Audit-class tables: the runtime role may insert and read, never change or delete.
APPEND_ONLY_TABLES: tuple[str, ...] = ("audit_rows",)

logger = structlog.get_logger(__name__)


class DatabaseRoleError(RuntimeError):
    """The database roles do not have the attributes tenancy relies on (D-014, D-021)."""


class StartupSeedError(RuntimeError):
    """A module seed cannot run: the seeded administrator does not exist."""


@dataclass(frozen=True, slots=True)
class RoleAttributes:
    name: str
    superuser: bool
    bypass_rls: bool


@asynccontextmanager
async def startup_lock(settings: DatabaseSettings) -> AsyncIterator[asyncpg.Connection]:
    """Hold the cluster-wide startup lock; yield the owner connection that holds it."""
    owner = settings.for_owner()
    connection = await asyncpg.connect(
        host=owner.db_host,
        port=owner.db_port,
        user=owner.db_user,
        password=owner.db_password.get_secret_value(),
        database=owner.db_name,
    )
    try:
        await connection.execute(f"SET lock_timeout = '{LOCK_TIMEOUT}'")
        logger.info("startup_lock_waiting")
        await connection.execute("SELECT pg_advisory_lock($1)", STARTUP_LOCK_ID)
        logger.info("startup_lock_acquired")
        try:
            yield connection
        finally:
            await connection.execute("SELECT pg_advisory_unlock($1)", STARTUP_LOCK_ID)
            logger.info("startup_lock_released")
    finally:
        await connection.close()


def role_problems(
    owner: RoleAttributes | None, runtime: RoleAttributes | None, runtime_is_owner_member: bool
) -> list[str]:
    """Why the roles cannot be trusted with row security; empty when they can."""
    problems = []
    if owner is None:
        problems.append("the migration owner role does not exist")
    else:
        if owner.superuser:
            problems.append("the migration owner role must not be a superuser")
        if not owner.bypass_rls:
            problems.append("the migration owner role must have BYPASSRLS")
    if runtime is None:
        problems.append("the runtime role does not exist")
    else:
        if runtime.superuser:
            problems.append("the runtime role must not be a superuser")
        if runtime.bypass_rls:
            problems.append("the runtime role must not have BYPASSRLS")
    if runtime_is_owner_member:
        problems.append("the runtime role must not be a member of the migration owner role")
    return problems


async def assert_database_roles(connection: asyncpg.Connection, settings: DatabaseSettings) -> None:
    """Raise DatabaseRoleError unless both roles have the attributes tenancy relies on."""
    rows = await connection.fetch(
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = ANY($1::text[])",
        [settings.db_owner_user, settings.db_user],
    )
    roles = {
        row["rolname"]: RoleAttributes(row["rolname"], row["rolsuper"], row["rolbypassrls"])
        for row in rows
    }
    owner, runtime = roles.get(settings.db_owner_user), roles.get(settings.db_user)
    is_member = False
    if owner is not None and runtime is not None:
        is_member = await connection.fetchval(
            "SELECT pg_has_role($1, $2, 'MEMBER')", runtime.name, owner.name
        )
    problems = role_problems(owner, runtime, is_member)
    if problems:
        raise DatabaseRoleError("; ".join(problems))
    logger.info("database_roles_verified")


async def apply_migrations(
    settings: DatabaseSettings, modules: Sequence[ModuleModels] = ()
) -> None:
    """Apply pending migrations as the migration owner. Call it while holding `startup_lock`."""
    try:
        await migrate(config=tortoise_config(settings.for_owner(), modules), progress=_log_progress)
        logger.info("migrations_up_to_date")
    finally:
        # The migration run opens its own Tortoise context; release its connections
        # before the seeds and the application open theirs.
        await Tortoise.close_connections()


async def grant_runtime_access(
    connection: asyncpg.Connection,
    runtime_role: str,
    append_only_tables: Sequence[str] = APPEND_ONLY_TABLES,
) -> None:
    """Give the runtime role data access to every table, append-only where required."""
    role = await connection.fetchval("SELECT quote_ident($1)", runtime_role)
    async with connection.transaction():
        await connection.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        await connection.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"
        )
        await connection.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        await connection.execute(f"REVOKE ALL ON TABLE {MIGRATIONS_TABLE} FROM {role}")
        for table in append_only_tables:
            name = await connection.fetchval("SELECT quote_ident($1)", table)
            await connection.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON TABLE {name} FROM {role}")
    logger.info("runtime_grants_applied")


@asynccontextmanager
async def owner_orm(
    settings: DatabaseSettings, modules: Sequence[ModuleModels]
) -> AsyncIterator[None]:
    """A Tortoise context on the owner's credentials for the seeds; always closed afterwards.

    No global fallback: the seeds run in this task, and the context must never become the
    one requests fall back to.
    """
    await Tortoise.init(config=tortoise_config(settings.for_owner(), modules))
    try:
        yield
    finally:
        await Tortoise.close_connections()


async def run_module_seeds(
    modules: Sequence[ModuleMount], admin_user_id: UUID | None, admin_username: str
) -> None:
    """Run each module's seed in registry order, after the core's admin seed."""
    seeds = [(module.name, module.seed) for module in modules if module.seed is not None]
    if not seeds:
        return
    if admin_user_id is None:
        raise StartupSeedError("module seeds need the seeded administrator, which does not exist")
    context = SeedContext(admin_user_id=admin_user_id, admin_username=admin_username)
    for name, seed in seeds:
        await seed(context)
        logger.info("module_seeded", module=name)


async def prepare_database(
    settings: DatabaseSettings,
    modules: Sequence[ModuleMount],
    *,
    seed_core: Callable[[], Awaitable[UUID | None]],
    admin_username: str,
) -> None:
    """Under the startup lock, as the owner: assert roles, migrate, grant, seed core then modules.

    `seed_core` is the core's admin seed; it returns the admin account's ID.
    """
    async with startup_lock(settings) as connection:
        await assert_database_roles(connection, settings)
        await apply_migrations(settings, modules)
        await grant_runtime_access(connection, settings.db_user, append_only_tables(modules))
        async with owner_orm(settings, modules):
            admin_user_id = await seed_core()
            await run_module_seeds(modules, admin_user_id, admin_username)


def append_only_tables(modules: Sequence[ModuleMount]) -> tuple[str, ...]:
    """The core's append-only tables followed by those the mounted modules declare."""
    declared = (table for module in modules for table in module.append_only_tables)
    return (*APPEND_ONLY_TABLES, *declared)


def _log_progress(action: str, app_label: str, migration: str) -> None:
    logger.info("migration_progress", action=action, app=app_label, migration=migration)

"""Building blocks for the work every replica does once at startup.

Role: `startup_lock` (a cluster-wide PostgreSQL advisory lock) and `apply_migrations`.
Used by: `backend.main` (the lifespan: migrations, then seeding, under the lock);
  tests/integration/test_migrations.py.
Depends on: asyncpg (a dedicated connection for the lock), Tortoise's built-in migrations,
  `backend.core.database` (`tortoise_config`, `ModuleModels`).
Key invariants: every replica runs the startup tasks, but the advisory lock serialises them —
  the first replica does the work, the others wait and find nothing left to do (template_core
  D-004). The lock lives on its own connection and is released if that connection drops, so a
  crashed replica never leaves it locked. The lock ID is a constant in code, not a setting, so
  every replica uses the same one; `lock_timeout` makes startup fail instead of waiting forever.
  Module migrations are applied with the core's in one graph (D-007).
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import asyncpg
import structlog
from tortoise import Tortoise
from tortoise.migrations.api import migrate

from backend.core.database import ModuleModels, tortoise_config
from backend.core.settings import DatabaseSettings

# Identifies "ethera-eval-core startup tasks" among PostgreSQL advisory locks. Not a secret:
# any number works as long as every replica uses the same one, which is why it is a
# constant in code rather than a setting that could differ between hosts.
STARTUP_LOCK_ID = 7_420_150_268_313_725_001
# Fail startup instead of waiting forever if another replica holds the lock too long.
LOCK_TIMEOUT = "120s"

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def startup_lock(settings: DatabaseSettings) -> AsyncIterator[None]:
    """Hold the cluster-wide startup lock for the duration of the block."""
    connection = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        database=settings.db_name,
    )
    try:
        await connection.execute(f"SET lock_timeout = '{LOCK_TIMEOUT}'")
        logger.info("startup_lock_waiting")
        await connection.execute("SELECT pg_advisory_lock($1)", STARTUP_LOCK_ID)
        logger.info("startup_lock_acquired")
        try:
            yield
        finally:
            await connection.execute("SELECT pg_advisory_unlock($1)", STARTUP_LOCK_ID)
            logger.info("startup_lock_released")
    finally:
        await connection.close()


async def apply_migrations(
    settings: DatabaseSettings, modules: Sequence[ModuleModels] = ()
) -> None:
    """Apply pending migrations. Call it while holding `startup_lock`."""
    try:
        await migrate(config=tortoise_config(settings, modules), progress=_log_progress)
        logger.info("migrations_up_to_date")
    finally:
        # The migration run opens its own Tortoise context; release its connections
        # before the application opens the real pool.
        await Tortoise.close_connections()


def _log_progress(action: str, app_label: str, migration: str) -> None:
    logger.info("migration_progress", action=action, app=app_label, migration=migration)

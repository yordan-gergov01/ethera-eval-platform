"""Tortoise ORM configuration and lifecycle.

Role: builds the Tortoise configuration (the core app `models` plus one app per mounted module),
  opens and closes the connection pool, and lists the driver errors that mean "PostgreSQL is
  unreachable".
Used by: `backend.main`, `backend.core.startup`, `backend.core.job_waiter`,
  `backend.core.modules`, `backend.messaging.consumers`, and the `backend` barrel (for
  `evals.migration_cli`).
Depends on: Tortoise ORM, asyncpg's exception classes, `backend.core.settings.DatabaseSettings`.
Key invariants: each module with models gets its own app label and migrations package, so no
  revision mixes core and module DDL (D-007); the core app label `models` is always present.
  `ModuleModels` is a Protocol free of HTTP types, so messaging and services can import this
  module. Only the listed connection errors become 503; any other database error is a bug and
  stays a 500. `_enable_global_fallback=True` is deliberate: the lifespan runs in another task
  than the requests, and Tortoise keeps its state in a context variable. UTC everywhere.
"""

import socket
from collections.abc import Sequence
from typing import Any, Protocol

from asyncpg import exceptions as pg
from tortoise import Tortoise

from backend.core.settings import DatabaseSettings

APP_LABEL = "models"
MIGRATIONS_MODULE = "migrations"


class ModuleModels(Protocol):
    """What the database layer needs from a mounted module (`backend.core.modules.ModuleMount`
    satisfies it); kept free of HTTP types so messaging and services can import this module."""

    @property
    def name(self) -> str: ...

    @property
    def models(self) -> tuple[str, ...]: ...

    @property
    def migrations(self) -> str | None: ...


# Exceptions that mean "PostgreSQL cannot be reached right now", as raised through
# Tortoise by the asyncpg driver. The application answers them with 503: the request
# was fine, a dependency is down. Anything else from the database (a broken query,
# a constraint violation) is a bug and stays a 500.
DATABASE_UNAVAILABLE_ERRORS: tuple[type[Exception], ...] = (
    ConnectionError,  # refused, reset, aborted; includes Tortoise's DBConnectionError
    socket.gaierror,  # the database host name cannot be resolved
    TimeoutError,  # connecting took too long
    pg.PostgresConnectionError,  # SQLSTATE class 08, e.g. the connection was lost
    pg.CannotConnectNowError,  # 57P03: the server is starting up or shutting down
    pg.AdminShutdownError,  # 57P01
    pg.CrashShutdownError,  # 57P02
    pg.TooManyConnectionsError,  # 53300
)


def tortoise_config(
    settings: DatabaseSettings, modules: Sequence[ModuleModels] = ()
) -> dict[str, Any]:
    """Build the Tortoise configuration: one PostgreSQL connection pool, UTC everywhere.

    The core's own app is always present; each mounted module with models adds its own
    app label and migrations package (D-007).
    """
    apps: dict[str, dict[str, Any]] = {
        APP_LABEL: {
            "models": ["common_lib.models"],
            "default_connection": "default",
            "migrations": MIGRATIONS_MODULE,
        }
    }
    for module in modules:
        if module.models:
            apps[module.name] = {
                "models": list(module.models),
                "default_connection": "default",
                "migrations": module.migrations,
            }
    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.asyncpg",
                "credentials": {
                    "host": settings.db_host,
                    "port": settings.db_port,
                    "user": settings.db_user,
                    "password": settings.db_password.get_secret_value(),
                    "database": settings.db_name,
                    "minsize": 1,
                    "maxsize": settings.db_pool_max_size,
                },
            }
        },
        "apps": apps,
        "use_tz": True,
        "timezone": "UTC",
    }


async def init_database(settings: DatabaseSettings, modules: Sequence[ModuleModels] = ()) -> None:
    """Open the connection pool and register the models.

    The ASGI lifespan runs in a different task from the requests, and Tortoise
    keeps its state in a context variable. The global fallback makes that state
    visible to every request task, as Tortoise's own FastAPI integration does.
    `close_database` clears it again.
    """
    await Tortoise.init(config=tortoise_config(settings, modules), _enable_global_fallback=True)


async def close_database() -> None:
    """Close every connection of the pool."""
    await Tortoise.close_connections()

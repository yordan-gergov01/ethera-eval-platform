"""How a domain module is mounted into the platform core.

Role: the one type through which domain modules (`evals/<module>`) plug into the core app:
  their router, their Tortoise models, their own migrations package and an optional startup
  seed; `SeedContext` is what a seed receives.
Used by: `backend.main.create_app`, `backend.core.startup` (runs the seeds) and `evals.MODULES`
  (through the `backend` barrel); the database layer reads it through the
  `backend.core.database.ModuleModels` Protocol.
Depends on: FastAPI's `APIRouter` type; the core app label from `backend.core.database`.
Key invariants: the core never names a domain module — it only receives `ModuleMount`
  values, so it boots with none (tests/integration/test_boot_without_evals.py). Each module
  is its own Tortoise app label with its own migrations package, so a migration revision can
  never mix core and module DDL (docs/DECISIONS.md D-007). Module names must not collide with
  the core app label `models`. A module's `seed` runs at every start, after the core's admin
  seed, under the startup lock, on the migration owner's connection (row security bypassed),
  so it must be create-only and idempotent; it receives IDs, never settings or secrets.
  `append_only_tables` names the module's own audit-class tables: the core grants the runtime
  role INSERT and SELECT only on them, as on its own (`backend.core.startup`), without ever
  naming a module table itself.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter

from backend.core.database import APP_LABEL as CORE_APP_LABEL


@dataclass(frozen=True, slots=True)
class SeedContext:
    """What a module seed receives: the seeded administrator (the actor of seeded changes)."""

    admin_user_id: UUID
    admin_username: str


type ModuleSeed = Callable[[SeedContext], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ModuleMount:
    """One domain module as the core sees it.

    `name` is the module's Tortoise app label; `models` its model modules (dotted paths);
    `migrations` its migrations package; `router` its `/api/v1` routes (rate limited and
    documented like the core's own); `seed` its idempotent startup seed, if any;
    `append_only_tables` its tables the runtime role may insert into and read, never change.
    """

    name: str
    router: APIRouter | None = None
    models: tuple[str, ...] = ()
    migrations: str | None = None
    seed: ModuleSeed | None = None
    append_only_tables: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.isidentifier() or self.name == CORE_APP_LABEL:
            raise ValueError(f"invalid module name {self.name!r}")
        if self.migrations is not None and not self.models:
            raise ValueError(f"module {self.name!r} has migrations but no models")
        for table in self.append_only_tables:
            if not table.isidentifier() or table != table.lower():
                raise ValueError(f"module {self.name!r}: invalid table name {table!r}")

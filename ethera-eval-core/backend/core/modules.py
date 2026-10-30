"""How a domain module is mounted into the platform core.

Role: the one type through which domain modules (`evals/<module>`) plug into the core app:
  their router, their Tortoise models and their own migrations package.
Used by: `backend.main.create_app` and `evals.MODULES` (through the `backend` barrel); the
  database layer reads it through the `backend.core.database.ModuleModels` Protocol.
Depends on: FastAPI's `APIRouter` type; the core app label from `backend.core.database`.
Key invariants: the core never names a domain module — it only receives `ModuleMount`
  values, so it boots with none (tests/integration/test_boot_without_evals.py). Each module
  is its own Tortoise app label with its own migrations package, so a migration revision can
  never mix core and module DDL (docs/DECISIONS.md D-007). Module names must not collide with
  the core app label `models`.
"""

from dataclasses import dataclass

from fastapi import APIRouter

from backend.core.database import APP_LABEL as CORE_APP_LABEL


@dataclass(frozen=True, slots=True)
class ModuleMount:
    """One domain module as the core sees it.

    `name` is the module's Tortoise app label; `models` its model modules (dotted paths);
    `migrations` its migrations package; `router` its `/api/v1` routes (rate limited and
    documented like the core's own).
    """

    name: str
    router: APIRouter | None = None
    models: tuple[str, ...] = ()
    migrations: str | None = None

    def __post_init__(self) -> None:
        if not self.name.isidentifier() or self.name == CORE_APP_LABEL:
            raise ValueError(f"invalid module name {self.name!r}")
        if self.migrations is not None and not self.models:
            raise ValueError(f"module {self.name!r} has migrations but no models")

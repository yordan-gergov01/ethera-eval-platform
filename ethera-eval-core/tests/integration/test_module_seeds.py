"""Module seeds at startup: after the admin seed, under the lock, as the owner, then gone.

Role: pins the `ModuleMount.seed` hook as `backend.main.create_app` runs it through
  backend.core.startup `prepare_database`: it receives the seeded administrator's ID, runs on
  the migration owner's connection while the startup lock is held, and the request pool that
  follows is the runtime role's; a failing seed stops startup without leaving an ORM context
  behind, so the next start succeeds.
Used by: pytest (integration — needs the test database).
Depends on: `backend_settings`, `connect_as_app` from tests/integration/conftest.py;
  `backend.main.create_app` with a probe `ModuleMount` (no router, no models); Tortoise's
  `connections`.
Key invariants: the probe module is defined here, never in `evals` — the core is exercised
  with a module it cannot name; at most one app is live at a time.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest
from tortoise import connections

from backend.core.modules import ModuleMount, SeedContext
from backend.core.settings import BackendSettings
from backend.core.startup import STARTUP_LOCK_ID
from backend.main import create_app
from tests.integration.conftest import connect_as_app


@dataclass
class SeedProbe:
    """Records what a module seed observes."""

    observed: list[dict[str, Any]] = field(default_factory=list)  # Any: query results

    async def seed(self, context: SeedContext) -> None:
        rows = await connections.get("default").execute_query_dict(
            "SELECT current_user AS role, "
            "(SELECT id FROM users WHERE username = $1) AS admin_id, "
            "EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND granted "
            "AND ((classid::bigint << 32) | objid::bigint) = $2) AS lock_held",
            [context.admin_username, STARTUP_LOCK_ID],
        )
        self.observed.append(rows[0] | {"context": context})


class SeedFailedError(Exception):
    pass


async def _failing_seed(context: SeedContext) -> None:
    raise SeedFailedError


async def test_module_seed_runs_after_the_admin_seed_as_owner_under_the_lock(
    backend_settings: BackendSettings,
) -> None:
    probe = SeedProbe()
    app = create_app(backend_settings, modules=[ModuleMount(name="seedprobe", seed=probe.seed)])

    async with app.router.lifespan_context(app):
        request_role = await connections.get("default").execute_query_dict(
            "SELECT current_user AS role"
        )

    [seen] = probe.observed
    assert seen["role"] == backend_settings.db_owner_user
    assert seen["admin_id"] == seen["context"].admin_user_id
    assert seen["context"].admin_username == backend_settings.admin_username
    assert seen["lock_held"] is True
    assert request_role == [{"role": backend_settings.db_user}]


async def test_module_seed_runs_on_every_start(backend_settings: BackendSettings) -> None:
    probe = SeedProbe()
    for _ in range(2):
        app = create_app(backend_settings, modules=[ModuleMount(name="seedprobe", seed=probe.seed)])
        async with app.router.lifespan_context(app):
            pass

    assert len(probe.observed) == 2
    assert probe.observed[0]["admin_id"] == probe.observed[1]["admin_id"]


async def test_failing_module_seed_stops_startup_and_leaves_nothing_open(
    backend_settings: BackendSettings,
) -> None:
    failing = create_app(backend_settings, modules=[ModuleMount(name="broken", seed=_failing_seed)])
    with pytest.raises(SeedFailedError):
        async with failing.router.lifespan_context(failing):
            pass

    # The lock was released and no ORM context leaked: a normal start succeeds.
    app = create_app(backend_settings)
    async with app.router.lifespan_context(app):
        rows = await connections.get("default").execute_query_dict("SELECT current_user AS r")
    assert rows == [{"r": backend_settings.db_user}]

    connection = await connect_as_app(backend_settings)
    try:
        admins = await connection.fetchval(
            "SELECT count(*) FROM users WHERE username = $1", backend_settings.admin_username
        )
    finally:
        await connection.close()
    assert admins == 1  # the admin seed ran before the module seed failed, and committed

"""Waking waiters through PostgreSQL LISTEN/NOTIFY, across backend replicas.

Role: pins backend.core.job_waiter `JobWaiter` on `JOB_EVENTS_CHANNEL`: a notification wakes
  every replica, a lost listener wakes every waiter and reconnects, an unannounced wait ends
  at its timeout.
Used by: pytest (integration — needs the test database).
Depends on: `fresh_database`, `SERVER`, `connect_as_app` from tests/integration/conftest.py.
Key invariants: each `JobWaiter` stands for one replica; the notifications are real `pg_notify`
  calls and the lost listener is a real `pg_terminate_backend`; missed notifications cannot
  be replayed, so a lost listener wakes everyone to look again.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from backend.core.job_events import JOB_EVENTS_CHANNEL
from backend.core.job_waiter import JobWaiter
from backend.core.settings import DatabaseSettings
from tests.integration.conftest import SERVER, connect_as_app


@asynccontextmanager
async def running(settings: DatabaseSettings) -> AsyncIterator[JobWaiter]:
    waiter = JobWaiter(settings, initial_delay=0.1)
    waiter.start()
    try:
        async with asyncio.timeout(10):
            await waiter.wait_until_listening()
        yield waiter
    finally:
        await waiter.close()


async def notify(settings: DatabaseSettings, payload: str) -> None:
    connection = await connect_as_app(settings)
    try:
        await connection.execute("SELECT pg_notify($1, $2)", JOB_EVENTS_CHANNEL, payload)
    finally:
        await connection.close()


async def test_a_notification_from_any_connection_wakes_every_replica(
    fresh_database: DatabaseSettings,
) -> None:
    job_id = uuid4()
    async with running(fresh_database) as first, running(fresh_database) as second:
        with first.watch(job_id) as on_first, second.watch(job_id) as on_second:
            await notify(fresh_database, str(job_id))

            async with asyncio.timeout(5):
                await on_first.wait()
                await on_second.wait()


async def test_a_lost_listener_wakes_every_waiter_and_reconnects(
    fresh_database: DatabaseSettings,
) -> None:
    job_id = uuid4()
    async with running(fresh_database) as waiter:
        with waiter.watch(job_id) as event:
            admin = await SERVER.connect_as_superuser(fresh_database.db_name)
            try:
                terminated = await admin.fetchval(
                    "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity "
                    "WHERE datname = $1 AND query LIKE 'LISTEN%'",
                    fresh_database.db_name,
                )
            finally:
                await admin.close()
            assert terminated == 1

            # Missed notifications cannot be replayed: everyone looks again.
            async with asyncio.timeout(5):
                await event.wait()

        async with asyncio.timeout(15):
            await waiter.wait_until_listening()
        with waiter.watch(job_id) as again:
            await notify(fresh_database, str(job_id))
            async with asyncio.timeout(5):
                await again.wait()


async def test_a_waiter_wakes_as_soon_as_its_job_is_announced(
    fresh_database: DatabaseSettings,
) -> None:
    job_id = uuid4()
    async with running(fresh_database) as waiter:
        with waiter.watch(job_id) as event:
            waiting = asyncio.create_task(asyncio.wait_for(event.wait(), timeout=20))
            await asyncio.sleep(0.3)
            started = asyncio.get_running_loop().time()

            await notify(fresh_database, str(job_id))
            await waiting

            assert asyncio.get_running_loop().time() - started < 5


async def test_a_wait_without_an_announcement_ends_at_its_timeout(
    fresh_database: DatabaseSettings,
) -> None:
    async with running(fresh_database) as waiter:
        with waiter.watch(uuid4()) as event:
            started = asyncio.get_running_loop().time()
            await notify(fresh_database, str(uuid4()))

            woken = True
            try:
                await asyncio.wait_for(event.wait(), timeout=1)
            except TimeoutError:
                woken = False

            assert woken is False
            assert 0.9 < asyncio.get_running_loop().time() - started < 5

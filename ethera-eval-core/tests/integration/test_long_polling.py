"""Long polling over HTTP: the waiter, the poll cap and the request rate limit together.

Role: pins how backend.core.long_poll `ConcurrentPollLimiter`, backend.core.job_waiter
  `JobWaiter`, `limit_requests` and the current-user dependency combine: a poll returns as soon
  as its job is announced or at its timeout, a fourth concurrent poll per user is 429, and each
  poll counts once against the request rate.
Used by: pytest (integration — needs the test database).
Depends on: `backend_settings`, `create_user`, `token_for`, `bearer`, `assert_problem`,
  `connect_as_app`, `ADMIN_PASSWORD` from tests/integration/conftest.py.
Key invariants: no endpoint polls a job yet (slice 003 adds one), so the test mounts a minimal
  poll route on the real application, built from the same parts the real one will use; jobs
  are announced by a real PostgreSQL NOTIFY.
"""

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies.auth import CurrentUserDep
from backend.api.dependencies.rate_limit import limit_requests
from backend.core.job_events import JOB_EVENTS_CHANNEL
from backend.core.job_waiter import JobWaiter
from backend.core.long_poll import ConcurrentPollLimiter
from backend.core.settings import BackendSettings
from backend.main import create_app
from tests.integration.conftest import (
    ADMIN_PASSWORD,
    assert_problem,
    bearer,
    connect_as_app,
    create_user,
    token_for,
)

POLL = "/api/v1/test-poll"
PASSWORD = "test-only-plain-user-password"
MAX_CONCURRENT_POLLS = 3


@dataclass(frozen=True)
class PollingBackend:
    client: AsyncClient
    settings: BackendSettings


@pytest.fixture
async def backend(backend_settings: BackendSettings) -> AsyncIterator[PollingBackend]:
    waiter = JobWaiter(backend_settings)
    slots = ConcurrentPollLimiter(MAX_CONCURRENT_POLLS)
    router = APIRouter(prefix=POLL, dependencies=[Depends(limit_requests)])

    @router.get("/{job_id}")
    async def poll(job_id: UUID, user: CurrentUserDep, wait_seconds: float = 0) -> dict[str, bool]:
        with slots.slot(user.id), waiter.watch(job_id) as event:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(event.wait(), timeout=wait_seconds)
            return {"woken": event.is_set()}

    app = create_app(backend_settings)
    app.include_router(router)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        waiter.start()
        try:
            async with asyncio.timeout(10):
                await waiter.wait_until_listening()
            yield PollingBackend(client=client, settings=backend_settings)
        finally:
            await waiter.close()


@pytest.fixture
async def dora(backend: PollingBackend) -> str:
    await create_user(backend.settings, username="dora", password=PASSWORD)
    return await token_for(backend.client, "dora", PASSWORD)


async def announce(settings: BackendSettings, job_id: UUID) -> None:
    connection = await connect_as_app(settings)
    try:
        await connection.execute("SELECT pg_notify($1, $2)", JOB_EVENTS_CHANNEL, str(job_id))
    finally:
        await connection.close()


async def test_a_waiting_poll_returns_as_soon_as_the_job_is_announced(
    backend: PollingBackend, dora: str
) -> None:
    job_id = uuid4()
    started = time.monotonic()
    poll = asyncio.create_task(
        backend.client.get(f"{POLL}/{job_id}", params={"wait_seconds": 20}, headers=bearer(dora))
    )
    await asyncio.sleep(0.5)

    await announce(backend.settings, job_id)
    response = await asyncio.wait_for(poll, timeout=10)

    assert (response.status_code, response.json()) == (200, {"woken": True})
    assert time.monotonic() - started < 10


async def test_a_poll_without_an_announcement_returns_at_the_timeout(
    backend: PollingBackend, dora: str
) -> None:
    started = time.monotonic()

    response = await backend.client.get(
        f"{POLL}/{uuid4()}", params={"wait_seconds": 1}, headers=bearer(dora)
    )

    assert (response.status_code, response.json()) == (200, {"woken": False})
    assert 0.9 < time.monotonic() - started < 5


async def test_a_fourth_concurrent_poll_is_429_and_other_users_are_unaffected(
    backend: PollingBackend, dora: str
) -> None:
    client = backend.client
    waiting = [
        asyncio.create_task(
            client.get(f"{POLL}/{uuid4()}", params={"wait_seconds": 3}, headers=bearer(dora))
        )
        for _ in range(MAX_CONCURRENT_POLLS)
    ]
    await asyncio.sleep(0.5)

    refused = await client.get(
        f"{POLL}/{uuid4()}", params={"wait_seconds": 3}, headers=bearer(dora)
    )
    admin = await token_for(client, "admin", ADMIN_PASSWORD)
    other = await client.get(f"{POLL}/{uuid4()}", params={"wait_seconds": 1}, headers=bearer(admin))

    assert_problem(refused, 429, "TOO_MANY_CONCURRENT_POLLS")
    assert refused.headers["retry-after"] == "1"
    # The request rate headers still describe the request rate limit.
    assert refused.headers["x-ratelimit-limit"] == "120"
    assert (other.status_code, other.json()) == (200, {"woken": False})
    assert {r.status_code for r in await asyncio.gather(*waiting)} == {200}


async def test_each_poll_counts_once_against_the_request_rate(
    backend: PollingBackend, dora: str
) -> None:
    job = f"{POLL}/{uuid4()}"
    before = await backend.client.get(job, headers=bearer(dora))

    after = await backend.client.get(job, params={"wait_seconds": 1}, headers=bearer(dora))

    remaining_before = int(before.headers["x-ratelimit-remaining"])
    assert int(after.headers["x-ratelimit-remaining"]) == remaining_before - 1

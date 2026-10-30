"""The PostgreSQL rate limit store: atomic counts shared by every connection.

Role: pins backend.dal.rate_limit `RateLimitRepository`: counts per key and window, reads the
  previous window, counts concurrent requests exactly, deletes old windows; and that the
  `rate_limit_cleanup` periodic task runs while the app runs.
Used by: pytest (integration — needs the test database).
Depends on: `started_app` from tests/integration/conftest.py (for the migrated schema and the
  initialised ORM).
Key invariants: 50 concurrent increments all see different counts, so none is lost or counted
  twice; window starts are fixed constants, never the wall clock.
"""

import asyncio

from httpx import AsyncClient

from backend.dal.rate_limit import RateLimitRepository, WindowCounts

WINDOW = 60
NOW_WINDOW = 1_800_000_000 - 1_800_000_000 % WINDOW


async def test_counts_requests_per_key_and_window(started_app: AsyncClient) -> None:
    store = RateLimitRepository()

    first = await store.increment("ip:a", window_start=NOW_WINDOW, window_seconds=WINDOW)
    second = await store.increment("ip:a", window_start=NOW_WINDOW, window_seconds=WINDOW)
    other_key = await store.increment("ip:b", window_start=NOW_WINDOW, window_seconds=WINDOW)

    assert (first, second, other_key) == (
        WindowCounts(current=1, previous=0),
        WindowCounts(current=2, previous=0),
        WindowCounts(current=1, previous=0),
    )


async def test_reads_the_previous_window(started_app: AsyncClient) -> None:
    store = RateLimitRepository()
    for _ in range(3):
        await store.increment("ip:a", window_start=NOW_WINDOW - WINDOW, window_seconds=WINDOW)

    counts = await store.increment("ip:a", window_start=NOW_WINDOW, window_seconds=WINDOW)

    assert counts == WindowCounts(current=1, previous=3)


async def test_concurrent_requests_are_all_counted(started_app: AsyncClient) -> None:
    store = RateLimitRepository()

    results = await asyncio.gather(
        *(
            store.increment("user:x", window_start=NOW_WINDOW, window_seconds=WINDOW)
            for _ in range(50)
        )
    )

    # Every request saw a different count: none was lost or counted twice.
    assert sorted(counts.current for counts in results) == list(range(1, 51))


async def test_old_windows_are_deleted(started_app: AsyncClient) -> None:
    store = RateLimitRepository()
    for window_start in (NOW_WINDOW - 2 * WINDOW, NOW_WINDOW - WINDOW, NOW_WINDOW):
        await store.increment("ip:a", window_start=window_start, window_seconds=WINDOW)

    deleted = await store.delete_windows_before(NOW_WINDOW - WINDOW)

    assert deleted == 1
    counts = await store.increment("ip:a", window_start=NOW_WINDOW, window_seconds=WINDOW)
    assert counts == WindowCounts(current=2, previous=1)


async def test_the_expired_window_cleanup_runs_while_the_app_runs(started_app: AsyncClient) -> None:
    # The periodic-task machinery's only job today; the job sweeper joins it in slice 003.
    assert "rate_limit_cleanup" in {task.get_name() for task in asyncio.all_tasks()}

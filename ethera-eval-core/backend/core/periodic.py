"""Background work that repeats while the application runs.

Role: `periodic_task`, an async context manager that runs an action every interval until the
  block exits.
Used by: `backend.main` (the rate limit cleanup task in the lifespan).
Depends on: asyncio, structlog.
Key invariants: a failing run is logged with its traceback and the next run happens on time — a
  briefly unreachable database must not stop the task for good. Each replica runs its own task,
  so the action must be safe to run concurrently. The first run happens after one interval, not
  at startup.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable

import structlog

logger = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def periodic_task(
    name: str, *, interval_seconds: float, action: Callable[[], Awaitable[object]]
) -> AsyncIterator[None]:
    """Run `action` every `interval_seconds` until the block exits.

    A failing run is logged with its traceback and the next run happens on time:
    a database that is briefly unreachable must not stop the task for good. Each
    replica runs its own task, so the action must be safe to run concurrently.
    """

    async def run_forever() -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await action()
            except Exception:
                logger.exception("periodic_task_failed", task=name)

    task = asyncio.create_task(run_forever(), name=name)
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

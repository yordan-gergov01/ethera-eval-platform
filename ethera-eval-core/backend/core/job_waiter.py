"""Waking requests that wait for a job, across all backend replicas.

Role: `JobWaiter` keeps one dedicated PostgreSQL connection per backend process listening on
  `job_events` and wakes this process's waiters for the announced job (template_core D-009).
Used by: no production code yet — it is generic machinery wired in slice 003 (D-006); exercised
  by tests/unit/backend/test_job_waiter.py and the integration tests of the waiter and of long
  polling.
Depends on: asyncpg (a dedicated connection, outside the Tortoise pool),
  `backend.core.job_events`, `backend.core.database.DATABASE_UNAVAILABLE_ERRORS`,
  `backend.core.settings.DatabaseSettings`.
Key invariants: the transaction that finishes a job must send the NOTIFY (the job repository's
  duty). Waiting holds no pooled connection and no transaction, only an `asyncio.Event` per
  waiting request. If the listening connection is lost, notifications sent meanwhile are lost
  too, so every waiter is woken to read the job again and the connection is re-established with
  capped exponential backoff; a lost listener is never propagated. A payload that is not a UUID
  is ignored.
"""

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import Iterator
from uuid import UUID

import asyncpg
import structlog

from backend.core.database import DATABASE_UNAVAILABLE_ERRORS
from backend.core.job_events import JOB_EVENTS_CHANNEL
from backend.core.settings import DatabaseSettings

logger = structlog.get_logger(__name__)

INITIAL_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 30.0
# Losing the listening connection, or the server refusing it, is retried.
LISTENER_ERRORS: tuple[type[BaseException], ...] = (
    *DATABASE_UNAVAILABLE_ERRORS,
    asyncpg.PostgresError,
)


class JobWaiter:
    def __init__(
        self,
        settings: DatabaseSettings,
        *,
        initial_delay: float = INITIAL_RETRY_DELAY_SECONDS,
        max_delay: float = MAX_RETRY_DELAY_SECONDS,
    ) -> None:
        self._settings = settings
        self._initial_delay = initial_delay
        self._max_delay = max_delay
        self._waiters: defaultdict[UUID, set[asyncio.Event]] = defaultdict(set)
        self._listening = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @contextlib.contextmanager
    def watch(self, job_id: UUID) -> Iterator[asyncio.Event]:
        """An event that is set when the job may have finished; removed on exit."""
        event = asyncio.Event()
        self._waiters[job_id].add(event)
        try:
            yield event
        finally:
            waiters = self._waiters[job_id]
            waiters.discard(event)
            if not waiters:
                del self._waiters[job_id]

    def start(self) -> None:
        self._task = asyncio.create_task(self._listen_forever(), name="job_events_listener")

    async def wait_until_listening(self) -> None:
        await self._listening.wait()

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def notify(self, job_id: UUID) -> None:
        """Wake the local waiters of one job."""
        for event in self._waiters.get(job_id, ()):
            event.set()

    def wake_all(self) -> None:
        for waiters in self._waiters.values():
            for event in waiters:
                event.set()

    async def _listen_forever(self) -> None:
        delay = self._initial_delay
        while True:
            # A lost listener is an expected outage: retried here, never propagated.
            try:
                await self._listen_once()
                delay = self._initial_delay
            except LISTENER_ERRORS as exc:
                logger.warning(
                    "job_events_unavailable", retry_in_seconds=delay, error=type(exc).__name__
                )
            self._listening.clear()
            # Notifications may have been missed; let every waiter look again.
            self.wake_all()
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._max_delay)

    async def _listen_once(self) -> None:
        settings = self._settings
        connection = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
            database=settings.db_name,
        )
        lost = asyncio.Event()
        connection.add_termination_listener(lambda _: lost.set())
        try:
            await connection.add_listener(JOB_EVENTS_CHANNEL, self._on_notification)
            self._listening.set()
            logger.info("job_events_listening")
            await lost.wait()
            logger.warning("job_events_connection_lost")
        finally:
            if not connection.is_closed():
                await connection.close()

    def _on_notification(self, _: object, __: int, ___: str, payload: object) -> None:
        try:
            job_id = UUID(str(payload))
        except ValueError:
            logger.warning("job_event_ignored", reason="not a job ID")
            return
        self.notify(job_id)

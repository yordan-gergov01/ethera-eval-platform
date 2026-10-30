"""Consuming jobs, answering them with a handler, and publishing the results.

Role: the generic `JobWorker` — a `JobHandler` turns one request payload into one result
  payload — and `declare_runner_topology`. Each job message ends in one of three ways:
  answered or failed with a code (the result is published with a confirm, and only then is the
  job acknowledged); unreadable (rejected without requeue, so it is dead-lettered and the backend
  fails the job as undeliverable); or the result cannot be published (the channel is closed,
  which returns the job to the queue as a failed delivery).
Used by: `runner.main` (`declare_runner_topology`); `JobWorker` has no production caller until
  slice 003 (D-006) and is exercised by tests/unit/runner/test_worker.py and the runner
  integration tests.
Depends on: `common_lib.messaging` (amqp, declare, envelope, jobs, topology), aio-pika.
Key invariants: at-least-once — the job is acknowledged only after the result is confirmed; the
  backend ignores duplicates (template_core D-010). On a publish failure the channel is closed
  rather than nacking: an unacknowledged message on an open channel is never redelivered, and an
  explicit requeue does not count towards the delivery limit, so a failing job would loop
  forever. A handler never decides a message's fate by raising: a timeout or unexpected error
  becomes a failed result built by its `failed`, with a closed `JobErrorCode`. The runner also
  declares the result queue, so results wait while the backend is down. `stop` leaves jobs still
  running after the grace for redelivery.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Protocol

import structlog
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustConnection,
)
from pydantic import ValidationError

from common_lib.messaging.amqp import envelope_message
from common_lib.messaging.declare import declare_topology
from common_lib.messaging.envelope import Envelope, envelope_type
from common_lib.messaging.jobs import JobErrorCode, JobPayload
from common_lib.messaging.topology import EXCHANGE, JOBS_QUEUE, RESULTS_QUEUE

logger = structlog.get_logger(__name__)

# A broker that has not confirmed a result in this time is treated as failed.
PUBLISH_TIMEOUT_SECONDS = 5.0


class JobHandler[RequestT: JobPayload, ResultT: JobPayload](Protocol):
    """Answers one kind of job. `failed` must not raise: it builds a result from a code."""

    async def handle(self, request: RequestT) -> ResultT: ...

    def failed(self, request: RequestT, error_code: JobErrorCode) -> ResultT: ...


async def declare_runner_topology(connection: AbstractRobustConnection) -> None:
    """Declare the job queue the runner consumes and the result queue it publishes to.

    Declaring the result queue too means a result is never unroutable while the
    backend is down or has not started yet; it waits in the queue instead.
    """
    async with connection.channel() as channel:
        await declare_topology(channel, (JOBS_QUEUE, RESULTS_QUEUE))


@dataclass(frozen=True, slots=True)
class _Session:
    """One consuming channel and the exchange results are published to on it."""

    channel: AbstractChannel
    exchange: AbstractExchange


class JobWorker[RequestT: JobPayload, ResultT: JobPayload]:
    def __init__(
        self,
        handler: JobHandler[RequestT, ResultT],
        *,
        request_type: type[RequestT],
        result_type: type[ResultT],
        handler_timeout_seconds: float,
        prefetch_count: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if request_type.MESSAGE_TYPE is not JOBS_QUEUE.message_type:
            raise ValueError(f"{JOBS_QUEUE.name} carries {JOBS_QUEUE.message_type}")
        if result_type.MESSAGE_TYPE is not RESULTS_QUEUE.message_type:
            raise ValueError(f"{RESULTS_QUEUE.name} carries {RESULTS_QUEUE.message_type}")
        self._handler = handler
        self._request_type = request_type
        self._handler_timeout = handler_timeout_seconds
        self._prefetch_count = prefetch_count
        self._clock = clock
        self._session: _Session | None = None
        self._queue: AbstractQueue | None = None
        self._consumer_tag: str | None = None
        self._reset = asyncio.Event()
        self._in_flight = 0
        self._idle = asyncio.Event()
        self._idle.set()

    async def serve(self, connection: AbstractRobustConnection) -> None:
        """Consume jobs, opening a fresh channel after every deliberate reset."""
        while True:
            await self._open_session(connection)
            await self._reset.wait()
            self._reset.clear()
            logger.warning("job_channel_reopening")

    async def stop(self, grace_seconds: float) -> None:
        """Stop taking jobs, let running ones finish within the grace, then close.

        Jobs still running after the grace stay unacknowledged; closing the channel
        returns them to the queue, so another worker (or this one after a restart)
        answers them.
        """
        if self._queue is not None and self._consumer_tag is not None:
            await self._queue.cancel(self._consumer_tag)
        try:
            async with asyncio.timeout(grace_seconds):
                await self._idle.wait()
        except TimeoutError:
            logger.warning("jobs_left_for_redelivery", count=self._in_flight)
        session, self._session = self._session, None
        if session is not None and not session.channel.is_closed:
            await session.channel.close()
        logger.info("job_consumer_stopped")

    async def answer(self, request: RequestT) -> ResultT:
        """The result for a job; every failure becomes a code, never an exception."""
        started = self._clock()
        # Each outcome of the handler maps to one result; nothing else escapes.
        try:
            async with asyncio.timeout(self._handler_timeout):
                result = await self._handler.handle(request)
        except TimeoutError:
            logger.warning("job_failed", error_code=JobErrorCode.HANDLER_TIMEOUT)
            return self._handler.failed(request, JobErrorCode.HANDLER_TIMEOUT)
        except Exception:
            logger.exception("job_failed", error_code=JobErrorCode.INTERNAL_ERROR)
            return self._handler.failed(request, JobErrorCode.INTERNAL_ERROR)
        logger.info("job_answered", duration_ms=int((self._clock() - started) * 1000))
        return result

    async def _open_session(self, connection: AbstractRobustConnection) -> None:
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        await channel.set_qos(prefetch_count=self._prefetch_count)
        session = _Session(channel, await channel.get_exchange(EXCHANGE, ensure=False))
        self._queue = await channel.get_queue(JOBS_QUEUE.name, ensure=False)
        self._consumer_tag = await self._queue.consume(partial(self._on_message, session))
        self._session = session
        logger.info("job_consumer_started", prefetch_count=self._prefetch_count)

    async def _on_message(self, session: _Session, message: AbstractIncomingMessage) -> None:
        self._in_flight += 1
        self._idle.clear()
        try:
            await self._handle(session, message)
        finally:
            self._in_flight -= 1
            if not self._in_flight:
                self._idle.set()

    async def _handle(self, session: _Session, message: AbstractIncomingMessage) -> None:
        try:
            envelope = envelope_type(self._request_type).model_validate_json(message.body)
        except ValidationError:
            logger.warning("job_rejected", reason="unreadable", message_id=message.message_id)
            await message.reject(requeue=False)
            return

        request = envelope.payload
        with structlog.contextvars.bound_contextvars(
            request_id=envelope.request_id, job_id=str(request.job_id)
        ):
            logger.info("job_consumed", message_type=request.MESSAGE_TYPE.value)
            result = await self.answer(request)
            # Any failure to hand the result to the broker resets the channel, below.
            try:
                await session.exchange.publish(
                    # Unparametrised on purpose: it serialises every field of the result.
                    envelope_message(Envelope.wrap(result, request_id=envelope.request_id)),
                    routing_key=RESULTS_QUEUE.routing_key,
                    mandatory=True,
                    timeout=PUBLISH_TIMEOUT_SECONDS,
                )
            except Exception:
                logger.exception("result_publish_failed")
                await self._reset_channel(session)
                return
            if session is not self._session:
                # Another job reset this channel meanwhile; this job will be redelivered.
                logger.info("job_left_for_redelivery")
                return
            await message.ack()

    async def _reset_channel(self, session: _Session) -> None:
        """Close the channel so its unacknowledged jobs are redelivered, then reopen."""
        if session is not self._session:
            return
        self._session = None
        await session.channel.close()
        self._reset.set()

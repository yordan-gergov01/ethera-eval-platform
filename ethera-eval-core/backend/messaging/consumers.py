"""Consuming job results and dead-lettered job requests, for any payload types.

Role: `JobConsumers` consumes `backend.runner.results` and `runner.jobs.dlq` and settles each
  message; what a result means is the `ResultRecorder`'s business. Every message ends in exactly
  one of three ways: handled (acknowledged); database unreachable (requeued after a short pause);
  invalid or an unexpected error (rejected without requeue, so a result lands in
  `backend.runner.results.dlq` for inspection).
Used by: no production code yet — generic machinery wired with its first recorder in slice 003
  (D-006); exercised by tests/unit/backend/test_job_consumers.py and the integration tests of
  job results and the runner worker.
Depends on: `backend.messaging.connection.BrokerConnection`, `common_lib.messaging` (envelope,
  `JobPayload`, topology), `backend.core.database.DATABASE_UNAVAILABLE_ERRORS`, aio-pika.
Key invariants: an explicit requeue does not count towards the delivery limit, so a long database
  outage cannot dead-letter results. Both recorder methods must be idempotent (delivery is at
  least once; results apply only to pending jobs — template_core D-010). A dead-lettered request
  is failed as undeliverable, its job ID read from the body or, failing that, the correlation ID.
  The payload types must match the queues' message types, checked at construction.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

import structlog
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import ValidationError

from backend.core.database import DATABASE_UNAVAILABLE_ERRORS
from backend.messaging.connection import BrokerConnection
from common_lib.messaging.envelope import envelope_type
from common_lib.messaging.jobs import JobPayload
from common_lib.messaging.topology import JOBS_QUEUE, RESULTS_QUEUE

logger = structlog.get_logger(__name__)

DATABASE_RETRY_DELAY_SECONDS = 2.0

Sleep = Callable[[float], Awaitable[None]]


class ResultRecorder[ResultT: JobPayload](Protocol):
    """Applies results to the backend's state; both methods are idempotent."""

    async def record_result(self, result: ResultT) -> bool: ...

    async def fail_undeliverable(self, job_id: UUID) -> bool: ...


class InvalidMessageError(Exception):
    """A message that can never be processed; it is rejected without requeue."""


class JobConsumers[ResultT: JobPayload]:
    """Consumes `backend.runner.results` and `runner.jobs.dlq` once the broker is reached.

    `result_type` parses results; `request_type` is the payload of the job queue, used
    to read the job ID of a dead-lettered request.
    """

    def __init__(
        self,
        broker: BrokerConnection,
        results: ResultRecorder[ResultT],
        *,
        result_type: type[ResultT],
        request_type: type[JobPayload],
        prefetch_count: int,
        retry_delay: float = DATABASE_RETRY_DELAY_SECONDS,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if result_type.MESSAGE_TYPE is not RESULTS_QUEUE.message_type:
            raise ValueError(f"{RESULTS_QUEUE.name} carries {RESULTS_QUEUE.message_type}")
        if request_type.MESSAGE_TYPE is not JOBS_QUEUE.message_type:
            raise ValueError(f"{JOBS_QUEUE.name} carries {JOBS_QUEUE.message_type}")
        self._broker = broker
        self._results = results
        self._result_type = result_type
        self._request_type = request_type
        self._prefetch_count = prefetch_count
        self._retry_delay = retry_delay
        self._sleep = sleep
        self._channel: AbstractChannel | None = None
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start consuming in the background as soon as the broker is connected."""
        self._task = asyncio.create_task(self._consume(), name="job_consumers")

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()

    async def on_result(self, message: AbstractIncomingMessage) -> None:
        await self._handle(message, self._apply_result)

    async def on_dead_letter(self, message: AbstractIncomingMessage) -> None:
        await self._handle(message, self._apply_dead_letter)

    async def _consume(self) -> None:
        connection = await self._broker.wait_until_connected()
        # A robust channel: after a reconnect the consumers are restored with it.
        self._channel = await connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch_count)
        results = await self._channel.get_queue(RESULTS_QUEUE.name, ensure=False)
        await results.consume(self.on_result)
        dead_letters = await self._channel.get_queue(JOBS_QUEUE.dead_letter_queue, ensure=False)
        await dead_letters.consume(self.on_dead_letter)
        logger.info("job_consumers_started", prefetch_count=self._prefetch_count)

    async def _handle(
        self,
        message: AbstractIncomingMessage,
        apply: Callable[[AbstractIncomingMessage], Awaitable[None]],
    ) -> None:
        # Each outcome below decides the message's fate, so the errors are caught here.
        try:
            await apply(message)
        except InvalidMessageError as exc:
            logger.warning("message_rejected", reason=str(exc), message_id=message.message_id)
            await message.reject(requeue=False)
            return
        except DATABASE_UNAVAILABLE_ERRORS as exc:
            logger.warning(
                "message_requeued_database_unavailable",
                message_id=message.message_id,
                error=type(exc).__name__,
            )
            await self._sleep(self._retry_delay)
            await message.nack(requeue=True)
            return
        except Exception:
            logger.exception("message_handling_failed", message_id=message.message_id)
            await message.reject(requeue=False)
            return
        await message.ack()

    async def _apply_result(self, message: AbstractIncomingMessage) -> None:
        try:
            envelope = envelope_type(self._result_type).model_validate_json(message.body)
        except ValidationError as exc:
            raise InvalidMessageError("not a valid job result") from exc
        with structlog.contextvars.bound_contextvars(
            request_id=envelope.request_id, job_id=str(envelope.payload.job_id)
        ):
            await self._results.record_result(envelope.payload)

    async def _apply_dead_letter(self, message: AbstractIncomingMessage) -> None:
        job_id = self._job_id_of_dead_letter(message)
        with structlog.contextvars.bound_contextvars(job_id=str(job_id)):
            await self._results.fail_undeliverable(job_id)

    def _job_id_of_dead_letter(self, message: AbstractIncomingMessage) -> UUID:
        """The job a dead-lettered request belongs to, even if its body was the problem."""
        try:
            envelope = envelope_type(self._request_type).model_validate_json(message.body)
        except ValidationError:
            pass
        else:
            return envelope.payload.job_id
        try:
            return UUID(str(message.correlation_id))
        except ValueError as exc:
            raise InvalidMessageError("dead letter without a job ID") from exc

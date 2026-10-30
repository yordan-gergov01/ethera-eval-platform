"""Publishing job requests to the runner, for any job payload and work queue.

Role: `JobPublisher.publish(payload, queue=..., request_id=...)` wraps the payload in an envelope
  and waits until the broker has taken it.
Used by: no production code yet — generic machinery wired in slice 003 (D-006); exercised by
  tests/integration/test_job_publisher.py and tests/integration/test_runner_worker.py.
Depends on: `backend.messaging.connection.BrokerConnection`, `common_lib.messaging` (amqp,
  envelope, jobs, topology), `common_lib.errors`, aio-pika.
Key invariants: messages are persistent, published with confirms and as mandatory, so a message
  the broker cannot route fails the publish instead of disappearing (template_core D-010). Every
  failure becomes `ServiceUnavailableError(BROKER_UNAVAILABLE)` and the caller decides what
  happens to the job. A payload whose type does not match the queue is a programming error
  (`ValueError`). The envelope is built unparametrised on purpose, so subclass fields are not
  dropped. Only the job ID and message type are logged, never the payload.
"""

import asyncio

import structlog
from aio_pika.abc import AbstractChannel, AbstractExchange
from aio_pika.exceptions import AMQPError

from backend.messaging.connection import BrokerConnection
from common_lib.errors import ErrorCode, ServiceUnavailableError
from common_lib.messaging.amqp import envelope_message
from common_lib.messaging.envelope import Envelope
from common_lib.messaging.jobs import JobPayload
from common_lib.messaging.topology import EXCHANGE, QueueSpec

logger = structlog.get_logger(__name__)

# A broker that has not confirmed a publish in this time is treated as unavailable.
PUBLISH_TIMEOUT_SECONDS = 5.0
BROKER_UNAVAILABLE_MESSAGE = "The job queue is temporarily unavailable. Try again shortly."


class JobPublisher:
    """Publishes a job payload to a work queue and waits until the broker has taken it.

    Messages are persistent, published with confirms and as mandatory: a message the
    broker cannot route is returned and fails the publish instead of disappearing.
    Every failure becomes `ServiceUnavailableError(BROKER_UNAVAILABLE)`, so the caller
    decides what happens to the job. Only the job ID and message type are logged: the
    payload may carry data that does not belong in the logs.
    """

    def __init__(self, broker: BrokerConnection) -> None:
        self._broker = broker
        self._channel: AbstractChannel | None = None
        self._lock = asyncio.Lock()

    async def publish(self, payload: JobPayload, *, queue: QueueSpec, request_id: str) -> None:
        if payload.MESSAGE_TYPE is not queue.message_type:
            # A programming error, not an outage: the queue would route it nowhere useful.
            raise ValueError(
                f"{payload.MESSAGE_TYPE} cannot be published to {queue.name}, "
                f"which carries {queue.message_type}"
            )
        # Unparametrised on purpose: Envelope[JobPayload] would drop the subclass's fields.
        message = envelope_message(Envelope.wrap(payload, request_id=request_id))
        try:
            exchange = await self._exchange()
            await exchange.publish(
                message,
                routing_key=queue.routing_key,
                mandatory=True,
                timeout=PUBLISH_TIMEOUT_SECONDS,
            )
        except (AMQPError, OSError, TimeoutError) as exc:
            logger.warning(
                "job_publish_failed", job_id=str(payload.job_id), error=type(exc).__name__
            )
            raise ServiceUnavailableError(
                BROKER_UNAVAILABLE_MESSAGE, code=ErrorCode.BROKER_UNAVAILABLE
            ) from exc
        logger.info(
            "job_published", job_id=str(payload.job_id), message_type=payload.MESSAGE_TYPE.value
        )

    async def _exchange(self) -> AbstractExchange:
        connection = self._broker.connection
        if connection is None or connection.is_closed:
            raise ConnectionError("not connected to the broker")
        async with self._lock:
            if self._channel is None or self._channel.is_closed:
                # Returned (unroutable) messages raise instead of being dropped.
                self._channel = await connection.channel(
                    publisher_confirms=True, on_return_raises=True
                )
        return await self._channel.get_exchange(EXCHANGE, ensure=False)

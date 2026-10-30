"""Declaring the RabbitMQ topology from `topology`, identically in every service.

Role: `declare_topology(channel, queues)` declares both exchanges and, per queue spec, its
  dead-letter queue and work queue.
Used by: `backend.messaging.connection`, `runner.worker`; the broker topology tests and the
  integration conftest.
Depends on: `common_lib.messaging.topology`, aio-pika.
Key invariants: declarations are idempotent, so each service declares what it needs at every
  (re)connect and the start order of the services does not matter. Each dead-letter queue is
  declared before its work queue, so nothing is dead-lettered into an exchange without a queue
  behind it. Dead-lettering itself is configured by broker policies, not queue arguments.
"""

from collections.abc import Iterable

from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel
from pamqp.common import FieldTable

from common_lib.messaging.topology import (
    DEAD_LETTER_EXCHANGE,
    EXCHANGE,
    QUEUE_ARGUMENTS,
    QueueSpec,
)


async def declare_topology(channel: AbstractChannel, queues: Iterable[QueueSpec]) -> None:
    """Declare both exchanges and, for each queue spec, its dead-letter queue and work queue."""
    exchange = await channel.declare_exchange(EXCHANGE, ExchangeType.DIRECT, durable=True)
    dead_letter_exchange = await channel.declare_exchange(
        DEAD_LETTER_EXCHANGE, ExchangeType.DIRECT, durable=True
    )
    arguments: FieldTable = {**QUEUE_ARGUMENTS}
    for spec in queues:
        dead_letters = await channel.declare_queue(
            spec.dead_letter_queue, durable=True, arguments=arguments
        )
        await dead_letters.bind(dead_letter_exchange, routing_key=spec.routing_key)
        work = await channel.declare_queue(spec.name, durable=True, arguments=arguments)
        await work.bind(exchange, routing_key=spec.routing_key)

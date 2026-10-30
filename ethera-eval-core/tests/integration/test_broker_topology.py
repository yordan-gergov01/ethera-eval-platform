"""The RabbitMQ topology and per-user permissions hold on the real test broker.

Role: pins common_lib.messaging.topology and `declare_topology` (exchange, job and result
  queues, dead-letter queues, `DELIVERY_LIMIT`) and the permissions of the broker users.
Used by: pytest (integration — needs the test database and broker).
Depends on: `empty_queues`, `backend_settings`, `broker_channel` from
  tests/integration/conftest.py; the users backend, runner and inspector of the test broker.
Key invariants: jobs are published mandatory, so an unroutable job raises; an explicit requeue
  does not count towards the delivery limit (RabbitMQ 4) but a crashed consumer does; nobody
  consumes a queue it does not own; the inspector reads dead letters but cannot publish or
  declare.
"""

import asyncio

import pytest
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from aiormq.exceptions import ChannelAccessRefused

from backend.core.settings import BackendSettings
from backend.main import create_app
from common_lib.messaging.declare import declare_topology
from common_lib.messaging.topology import (
    DELIVERY_LIMIT,
    EXCHANGE,
    JOBS_QUEUE,
    RESULTS_QUEUE,
)
from tests.integration.conftest import broker_channel

pytestmark = pytest.mark.usefixtures("empty_queues")


async def publish_job(channel: AbstractChannel, body: bytes = b"{}") -> None:
    exchange = await channel.get_exchange(EXCHANGE, ensure=False)
    await exchange.publish(
        Message(body, delivery_mode=DeliveryMode.PERSISTENT),
        routing_key=JOBS_QUEUE.routing_key,
        mandatory=True,
    )


async def get_one(channel: AbstractChannel, queue: str) -> AbstractIncomingMessage:
    async with asyncio.timeout(10):
        while True:
            message = await (await channel.get_queue(queue, ensure=False)).get(fail=False)
            if message is not None:
                return message
            await asyncio.sleep(0.05)


async def test_backend_declares_the_job_queue_so_no_job_is_lost(
    backend_settings: BackendSettings,
) -> None:
    app = create_app(backend_settings)
    async with app.router.lifespan_context(app):
        connection = await app.state.broker.wait_until_connected()
        async with connection.channel() as channel:
            # Mandatory: an unroutable job would raise here instead of disappearing.
            await publish_job(channel, b'{"job": 1}')

    # The runner has never run; the job waits for it.
    async with broker_channel("runner") as channel:
        message = await get_one(channel, JOBS_QUEUE.name)
        await message.ack()
    assert message.body == b'{"job": 1}'


async def test_the_runner_can_declare_its_own_queues() -> None:
    async with broker_channel("runner") as channel:
        await declare_topology(channel, (JOBS_QUEUE,))


async def test_a_rejected_job_is_dead_lettered_and_readable_by_the_inspector() -> None:
    async with broker_channel("backend") as channel:
        await publish_job(channel, b"not a valid envelope")
    async with broker_channel("runner") as channel:
        await (await get_one(channel, JOBS_QUEUE.name)).reject(requeue=False)

    async with broker_channel("inspector") as channel:
        dead = await get_one(channel, JOBS_QUEUE.dead_letter_queue)
        await dead.nack(requeue=True)
    assert dead.body == b"not a valid envelope"


async def test_an_explicit_requeue_never_reaches_the_delivery_limit() -> None:
    # RabbitMQ 4 does not count requeues towards the delivery limit, so a consumer that
    # requeues a message it cannot process would loop on it forever. The runner
    # therefore rejects such messages instead (see the rejection test above).
    async with broker_channel("backend") as channel:
        await publish_job(channel, b"requeued again and again")

    async with broker_channel("runner") as channel:
        queue = await channel.get_queue(JOBS_QUEUE.name, ensure=False)
        for _ in range(DELIVERY_LIMIT + 3):
            message = await get_one(channel, JOBS_QUEUE.name)
            await message.nack(requeue=True)
        still_there = await get_one(channel, JOBS_QUEUE.name)
        await still_there.ack()
        assert await queue.get(fail=False) is None

    assert still_there.body == b"requeued again and again"
    async with broker_channel("backend") as channel:
        dead_letters = await channel.get_queue(JOBS_QUEUE.dead_letter_queue, ensure=False)
        assert await dead_letters.get(fail=False) is None


async def test_a_job_that_keeps_crashing_its_consumer_stops_at_the_delivery_limit() -> None:
    async with broker_channel("backend") as channel:
        await publish_job(channel, b"crashes its consumer")

    # A consumer that dies with the job unacknowledged returns it to the queue, and the
    # broker counts that. (An explicit requeue does not count in RabbitMQ 4.)
    deliveries = 0
    for _ in range(DELIVERY_LIMIT + 2):
        async with broker_channel("runner") as channel:
            queue = await channel.get_queue(JOBS_QUEUE.name, ensure=False)
            if await queue.get(fail=False) is None:
                break
            deliveries += 1
        await asyncio.sleep(0.1)

    async with broker_channel("backend") as channel:
        dead = await get_one(channel, JOBS_QUEUE.dead_letter_queue)
        await dead.ack()
    assert dead.body == b"crashes its consumer"
    # The first delivery plus DELIVERY_LIMIT counted returns, then dead-lettered.
    assert deliveries == DELIVERY_LIMIT + 1


@pytest.mark.parametrize(
    ("user", "queue"),
    [
        ("backend", JOBS_QUEUE.name),
        ("runner", RESULTS_QUEUE.name),
        ("runner", JOBS_QUEUE.dead_letter_queue),
        ("inspector", JOBS_QUEUE.name),
        ("inspector", RESULTS_QUEUE.name),
    ],
)
async def test_nobody_consumes_a_queue_it_does_not_own(user: str, queue: str) -> None:
    with pytest.raises(ChannelAccessRefused):
        async with broker_channel(user) as channel:
            await (await channel.get_queue(queue, ensure=False)).get(fail=False)


async def test_the_inspector_can_read_but_not_publish_or_declare() -> None:
    for queue in (JOBS_QUEUE.dead_letter_queue, RESULTS_QUEUE.dead_letter_queue):
        async with broker_channel("inspector") as channel:
            await (await channel.get_queue(queue, ensure=False)).get(fail=False)

    with pytest.raises(ChannelAccessRefused):
        async with broker_channel("inspector") as channel:
            await publish_job(channel)
    with pytest.raises(ChannelAccessRefused):
        async with broker_channel("inspector") as channel:
            await channel.declare_queue("inspector.scratch", durable=True)

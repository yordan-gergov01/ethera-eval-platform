"""Results and dead letters arriving through the real broker reach the result recorder.

Role: pins backend.messaging.consumers `JobConsumers` on a real broker: a result is recorded and
  acknowledged, a duplicate is left to the recorder, a result is requeued while the database is
  down, an invalid result is dead-lettered, and a dead-lettered request fails its job as
  undeliverable.
Used by: pytest (integration — needs the test database and broker).
Depends on: `empty_queues`, `BROKER`, `broker_channel`, `eventually` from
  tests/integration/conftest.py; `Ping`/`Pong`, `ping`, `pong_for`, `failed_pong` from
  tests/job_payloads.py; the local `Recorder`, an in-memory stand-in for the result store.
Key invariants: the consumers run on the backend's own broker user and real queues, on
  test-local payloads (docs/DECISIONS.md D-006); what a result means for the database arrives
  with the first real payload (slice 003), so the recorder is in memory and can fail like an
  unreachable database.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

import pytest
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractIncomingMessage

from backend.messaging.connection import BrokerConnection
from backend.messaging.consumers import JobConsumers
from common_lib.messaging.connection import robust_connector
from common_lib.messaging.envelope import Envelope
from common_lib.messaging.jobs import JobErrorCode, JobResultStatus
from common_lib.messaging.topology import EXCHANGE, JOBS_QUEUE, RESULTS_QUEUE
from tests.integration.conftest import BROKER, broker_channel, eventually
from tests.job_payloads import Ping, Pong, failed_pong, ping, pong_for

pytestmark = pytest.mark.usefixtures("empty_queues")


class Recorder:
    """Records what the consumers hand over; can fail like an unreachable database."""

    def __init__(self) -> None:
        self.results: list[Pong] = []
        self.undeliverable: list[UUID] = []
        self.outages = 0

    async def record_result(self, result: Pong) -> bool:
        if self.outages:
            self.outages -= 1
            raise ConnectionRefusedError
        if any(r.job_id == result.job_id for r in self.results):
            return False
        self.results.append(result)
        return True

    async def fail_undeliverable(self, job_id: UUID) -> bool:
        self.undeliverable.append(job_id)
        return True


@pytest.fixture
async def recorder() -> AsyncIterator[Recorder]:
    recorder = Recorder()
    broker = BrokerConnection(
        robust_connector(BROKER.settings_for("backend"), connection_name="backend-test")
    )
    consumers = JobConsumers(
        broker,
        recorder,
        result_type=Pong,
        request_type=Ping,
        prefetch_count=10,
        retry_delay=0.1,
    )
    broker.start()
    consumers.start()
    try:
        async with asyncio.timeout(15):
            await broker.wait_until_connected()
        yield recorder
    finally:
        await consumers.close()
        await broker.close()


async def publish(user: str, routing_key: str, body: bytes) -> None:
    async with broker_channel(user) as channel:
        exchange = await channel.get_exchange(EXCHANGE, ensure=False)
        await exchange.publish(
            Message(body, delivery_mode=DeliveryMode.PERSISTENT),
            routing_key=routing_key,
            mandatory=True,
        )


async def take_one(user: str, queue_name: str) -> AbstractIncomingMessage:
    """Get one message, unacknowledged; the caller settles it before the channel closes."""
    async with broker_channel(user) as channel:
        queue = await channel.get_queue(queue_name, ensure=False)
        for _ in range(100):
            message = await queue.get(fail=False, no_ack=True)
            if message is not None:
                return message
            await asyncio.sleep(0.1)
    raise AssertionError(f"no message in {queue_name}")


def body(result: Pong) -> bytes:
    return Envelope[Pong].wrap(result, request_id="req-1").model_dump_json().encode()


def recorded(recorder: Recorder, count: int) -> Callable[[], Awaitable[bool]]:
    async def check() -> bool:
        return len(recorder.results) >= count

    return check


async def queue_is_empty(user: str, queue_name: str) -> bool:
    async with broker_channel(user) as channel:
        queue = await channel.get_queue(queue_name, ensure=False)
        message = await queue.get(fail=False)
        if message is not None:
            await message.nack(requeue=True)
        return message is None


async def test_a_result_is_recorded_and_acknowledged(recorder: Recorder) -> None:
    request = ping("Hi")

    await publish("runner", RESULTS_QUEUE.routing_key, body(pong_for(request, "An answer")))
    await eventually(recorded(recorder, 1))

    [result] = recorder.results
    assert (result.job_id, result.status, result.text) == (
        request.job_id,
        JobResultStatus.COMPLETED,
        "An answer",
    )
    assert await queue_is_empty("backend", RESULTS_QUEUE.name)
    assert await queue_is_empty("inspector", RESULTS_QUEUE.dead_letter_queue)


async def test_a_failure_result_carries_its_error_code(recorder: Recorder) -> None:
    request = ping()

    await publish(
        "runner",
        RESULTS_QUEUE.routing_key,
        body(failed_pong(request, JobErrorCode.HANDLER_TIMEOUT)),
    )
    await eventually(recorded(recorder, 1))

    assert recorder.results[0].error_code is JobErrorCode.HANDLER_TIMEOUT


async def test_a_duplicate_result_is_acknowledged_and_left_to_the_recorder(
    recorder: Recorder,
) -> None:
    request = ping()
    await publish("runner", RESULTS_QUEUE.routing_key, body(pong_for(request)))
    await publish(
        "runner", RESULTS_QUEUE.routing_key, body(failed_pong(request, JobErrorCode.INTERNAL_ERROR))
    )
    await eventually(recorded(recorder, 1))
    await asyncio.sleep(1)

    assert [r.status for r in recorder.results] == [JobResultStatus.COMPLETED]
    assert await queue_is_empty("backend", RESULTS_QUEUE.name)
    assert await queue_is_empty("inspector", RESULTS_QUEUE.dead_letter_queue)


async def test_a_result_is_requeued_while_the_database_is_down_then_recorded(
    recorder: Recorder,
) -> None:
    recorder.outages = 2
    request = ping()

    await publish("runner", RESULTS_QUEUE.routing_key, body(pong_for(request)))
    await eventually(recorded(recorder, 1))

    assert recorder.outages == 0
    assert [r.job_id for r in recorder.results] == [request.job_id]
    assert await queue_is_empty("inspector", RESULTS_QUEUE.dead_letter_queue)


async def test_an_invalid_result_lands_in_the_result_dead_letter_queue(
    recorder: Recorder,
) -> None:
    await publish("runner", RESULTS_QUEUE.routing_key, b"not a valid envelope")

    dead = await take_one("inspector", RESULTS_QUEUE.dead_letter_queue)

    assert dead.body == b"not a valid envelope"
    assert recorder.results == []


async def test_a_dead_lettered_request_fails_its_job_as_undeliverable(
    recorder: Recorder,
) -> None:
    request = ping()
    request_body = Envelope[Ping].wrap(request, request_id="req-1").model_dump_json().encode()
    await publish("backend", JOBS_QUEUE.routing_key, request_body)

    # The runner rejects it, so the broker dead-letters it to the backend.
    async with broker_channel("runner") as channel:
        queue = await channel.get_queue(JOBS_QUEUE.name, ensure=False)
        for _ in range(100):
            message = await queue.get(fail=False)
            if message is not None:
                await message.reject(requeue=False)
                break
            await asyncio.sleep(0.1)

    async def failed() -> bool:
        return recorder.undeliverable == [request.job_id]

    await eventually(failed)

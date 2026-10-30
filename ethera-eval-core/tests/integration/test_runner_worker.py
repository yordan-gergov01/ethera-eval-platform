"""The runner's worker against the real broker, alone and with the backend's machinery.

Role: pins runner.worker `JobWorker` end to end: `JobPublisher` on the backend's user publishes
  a `Ping`, the worker answers it, and `JobConsumers` hands the `Pong` to a recorder; handler
  errors and timeouts fail the job with their code; unreadable jobs and unpublishable results
  end in the dead-letter queue.
Used by: pytest (integration — needs the test database and broker).
Depends on: `empty_queues`, `BROKER`, `broker_channel`, `eventually` from
  tests/integration/conftest.py; `EchoHandler`, `Ping`/`Pong`, `ping` from tests/job_payloads.py;
  the local in-memory `Recorder`.
Key invariants: runs on test-local payloads (docs/DECISIONS.md D-006) over the real test broker,
  never mocking our own messaging code; the runner declares the result queue itself, so results
  are kept while the backend is away; a result the broker returns sends the job back until the
  delivery limit dead-letters it.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from aio_pika import Message

from backend.messaging.connection import BrokerConnection
from backend.messaging.consumers import JobConsumers
from backend.messaging.publisher import JobPublisher
from common_lib.messaging.amqp import envelope_message
from common_lib.messaging.connection import connect_with_retry, robust_connector
from common_lib.messaging.envelope import Envelope, envelope_type
from common_lib.messaging.jobs import JobErrorCode, JobResultStatus
from common_lib.messaging.topology import DELIVERY_LIMIT, EXCHANGE, JOBS_QUEUE, RESULTS_QUEUE
from runner.worker import JobWorker, declare_runner_topology
from tests.integration.conftest import BROKER, broker_channel, eventually
from tests.job_payloads import EchoHandler, Ping, Pong, ping

pytestmark = pytest.mark.usefixtures("empty_queues")


@asynccontextmanager
async def running_worker(handler: EchoHandler) -> AsyncIterator[JobWorker[Ping, Pong]]:
    connection = await connect_with_retry(
        robust_connector(BROKER.settings_for("runner"), connection_name="runner-test"),
        setup=declare_runner_topology,
    )
    worker = JobWorker(
        handler,
        request_type=Ping,
        result_type=Pong,
        handler_timeout_seconds=1,
        prefetch_count=10,
    )
    task = asyncio.create_task(worker.serve(connection))
    try:
        yield worker
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await connection.close()


class Recorder:
    def __init__(self) -> None:
        self.results: list[Pong] = []
        self.undeliverable: list[UUID] = []

    async def record_result(self, result: Pong) -> bool:
        self.results.append(result)
        return True

    async def fail_undeliverable(self, job_id: UUID) -> bool:
        self.undeliverable.append(job_id)
        return True


@asynccontextmanager
async def running_backend() -> AsyncIterator[tuple[JobPublisher, Recorder]]:
    """The backend's messaging parts on its own broker user, with an in-memory recorder."""
    recorder = Recorder()
    broker = BrokerConnection(
        robust_connector(BROKER.settings_for("backend"), connection_name="backend-test")
    )
    consumers = JobConsumers(
        broker, recorder, result_type=Pong, request_type=Ping, prefetch_count=10
    )
    broker.start()
    consumers.start()
    try:
        async with asyncio.timeout(15):
            await broker.wait_until_connected()
        yield JobPublisher(broker), recorder
    finally:
        await consumers.close()
        await broker.close()


async def answered(recorder: Recorder) -> Pong:
    async def arrived() -> bool:
        return bool(recorder.results)

    await eventually(arrived)
    [result] = recorder.results
    return result


async def test_a_job_is_answered_end_to_end() -> None:
    request = ping("What is AMQP?")
    async with running_backend() as (publisher, recorder), running_worker(EchoHandler()):
        await publisher.publish(request, queue=JOBS_QUEUE, request_id="req-e2e")
        result = await answered(recorder)

    assert (result.job_id, result.status, result.text) == (
        request.job_id,
        JobResultStatus.COMPLETED,
        "echo: What is AMQP?",
    )


@pytest.mark.parametrize(
    ("handler", "code"),
    [
        (EchoHandler(error=RuntimeError("a bug")), JobErrorCode.INTERNAL_ERROR),
        (EchoHandler(delay=5), JobErrorCode.HANDLER_TIMEOUT),
    ],
    ids=["handler error", "handler timeout"],
)
async def test_a_failing_handler_fails_the_job_with_its_code(
    handler: EchoHandler, code: JobErrorCode
) -> None:
    request = ping()
    async with running_backend() as (publisher, recorder), running_worker(handler):
        await publisher.publish(request, queue=JOBS_QUEUE, request_id="req-fail")
        result = await answered(recorder)

    assert (result.job_id, result.status, result.error_code, result.text) == (
        request.job_id,
        JobResultStatus.FAILED,
        code,
        None,
    )


async def test_an_unreadable_job_is_dead_lettered_and_fails_as_undeliverable() -> None:
    job_id = ping().job_id
    handler = EchoHandler()
    async with running_backend() as (_, recorder), running_worker(handler):
        async with broker_channel("backend") as channel:
            exchange = await channel.get_exchange(EXCHANGE, ensure=False)
            await exchange.publish(
                Message(b"not a job", correlation_id=str(job_id)),
                routing_key=JOBS_QUEUE.routing_key,
                mandatory=True,
            )

        async def failed() -> bool:
            return recorder.undeliverable == [job_id]

        await eventually(failed)

    assert handler.calls == 0
    assert recorder.results == []


async def publish_job(text: str = "Hi") -> Ping:
    request = ping(text)
    async with broker_channel("backend") as channel:
        exchange = await channel.get_exchange(EXCHANGE, ensure=False)
        envelope = Envelope[Ping].wrap(request, request_id="req-runner")
        await exchange.publish(
            envelope_message(envelope),
            routing_key=JOBS_QUEUE.routing_key,
            mandatory=True,
        )
    return request


async def test_the_runner_declares_the_result_queue_while_the_backend_is_away() -> None:
    async with broker_channel("backend") as channel:
        for queue in (RESULTS_QUEUE.name, RESULTS_QUEUE.dead_letter_queue):
            await (await channel.get_queue(queue, ensure=False)).delete(
                if_unused=False, if_empty=False
            )

    async with running_worker(EchoHandler()):
        request = await publish_job()
        async with broker_channel("backend") as channel:
            results = await channel.get_queue(RESULTS_QUEUE.name, ensure=False)
            for _ in range(100):
                message = await results.get(fail=False)
                if message is not None:
                    break
                await asyncio.sleep(0.1)
            assert message is not None
            await message.ack()

    result = envelope_type(Pong).model_validate_json(message.body)
    assert (result.payload.job_id, result.request_id) == (request.job_id, "req-runner")
    assert result.payload.text == "echo: Hi"


async def test_a_result_that_cannot_be_published_returns_the_job_until_it_is_dead_lettered() -> (
    None
):
    handler = EchoHandler()
    async with running_worker(handler):
        # Without the result queue, every mandatory publish is returned by the broker.
        async with broker_channel("backend") as channel:
            await (await channel.get_queue(RESULTS_QUEUE.name, ensure=False)).delete(
                if_unused=False, if_empty=False
            )
        request = await publish_job()

        async with broker_channel("backend") as channel:
            dead_letters = await channel.get_queue(JOBS_QUEUE.dead_letter_queue, ensure=False)
            for _ in range(150):
                dead = await dead_letters.get(fail=False)
                if dead is not None:
                    break
                await asyncio.sleep(0.1)
            assert dead is not None
            await dead.ack()

    assert envelope_type(Ping).model_validate_json(dead.body).payload == request
    # Each closed channel returned the job as a failed delivery, up to the limit.
    assert handler.calls == DELIVERY_LIMIT + 1

"""The runner process and the worker's graceful stop, against the real broker.

Role: pins runner.main `run` (declares its queues, stops cleanly, stops promptly without a
  broker) and runner.worker `JobWorker.stop` (a running job finishes within the grace period;
  one that outlasts it is left for redelivery).
Used by: pytest (integration — needs the test database and broker).
Depends on: `empty_queues`, `BROKER`, `broker_channel`, `eventually` from
  tests/integration/conftest.py; `EchoHandler`, `Ping`/`Pong`, `ping` from tests/job_payloads.py.
Key invariants: runs on test-local payloads (docs/DECISIONS.md D-006); the runner serves no
  handler yet (slice 003), so a job published to it waits in its queue; a job that outlasts the
  grace period stays unacknowledged, so the broker redelivers it.
"""

import asyncio
import contextlib
import time

import pytest
from aio_pika.abc import AbstractRobustConnection
from aiormq.exceptions import ChannelNotFoundEntity

from common_lib.messaging.amqp import envelope_message
from common_lib.messaging.connection import connect_with_retry, robust_connector
from common_lib.messaging.envelope import Envelope, envelope_type
from common_lib.messaging.topology import EXCHANGE, JOBS_QUEUE, RESULTS_QUEUE
from runner.main import run
from runner.settings import RunnerSettings
from runner.worker import JobWorker, declare_runner_topology
from tests.integration.conftest import BROKER, broker_channel, eventually
from tests.job_payloads import EchoHandler, Ping, Pong, ping

pytestmark = pytest.mark.usefixtures("empty_queues")


def runner_settings(**overrides: object) -> RunnerSettings:
    values = BROKER.settings_for("runner").model_dump()
    return RunnerSettings.model_validate(values | overrides)


async def publish_job() -> Ping:
    request = ping("Hi")
    async with broker_channel("backend") as channel:
        exchange = await channel.get_exchange(EXCHANGE, ensure=False)
        await exchange.publish(
            envelope_message(Envelope[Ping].wrap(request, request_id="req-life")),
            routing_key=JOBS_QUEUE.routing_key,
            mandatory=True,
        )
    return request


async def next_message(user: str, queue_name: str, seconds: float = 10) -> bytes | None:
    async with broker_channel(user) as channel:
        queue = await channel.get_queue(queue_name, ensure=False)
        for _ in range(int(seconds * 10)):
            message = await queue.get(fail=False)
            if message is not None:
                await message.ack()
                return message.body
            await asyncio.sleep(0.1)
    return None


async def results_queue_exists() -> bool:
    try:
        async with broker_channel("backend") as channel:
            await channel.get_queue(RESULTS_QUEUE.name, ensure=True)
    except ChannelNotFoundEntity:
        return False
    return True


async def test_the_runner_declares_its_queues_and_stops_cleanly() -> None:
    async with broker_channel("backend") as channel:
        for queue in (RESULTS_QUEUE.name, JOBS_QUEUE.name):
            await (await channel.get_queue(queue, ensure=False)).delete(
                if_unused=False, if_empty=False
            )
    assert not await results_queue_exists()
    stop = asyncio.Event()
    service = asyncio.create_task(run(runner_settings(), stop))

    await eventually(results_queue_exists)
    # Mandatory: an undeclared job queue would make this publish fail.
    request = await publish_job()
    stop.set()
    async with asyncio.timeout(15):
        await service

    # No handler is served yet (slice 003): the job waits in its queue.
    body = await next_message("runner", JOBS_QUEUE.name)
    assert body is not None
    assert envelope_type(Ping).model_validate_json(body).payload == request


async def test_stopping_without_a_broker_ends_promptly() -> None:
    stop = asyncio.Event()
    service = asyncio.create_task(run(runner_settings(rabbitmq_port=1), stop))
    await asyncio.sleep(0.5)

    started = time.monotonic()
    stop.set()
    async with asyncio.timeout(5):
        await service

    assert time.monotonic() - started < 5


async def worker_with(
    handler: EchoHandler,
) -> tuple[JobWorker[Ping, Pong], asyncio.Task[None], AbstractRobustConnection]:
    connection = await connect_with_retry(
        robust_connector(BROKER.settings_for("runner"), connection_name="runner-test"),
        setup=declare_runner_topology,
    )
    worker = JobWorker(
        handler,
        request_type=Ping,
        result_type=Pong,
        handler_timeout_seconds=60,
        prefetch_count=1,
    )
    return worker, asyncio.create_task(worker.serve(connection)), connection


async def test_a_running_job_finishes_within_the_grace_period() -> None:
    handler = EchoHandler(delay=1)
    worker, serving, connection = await worker_with(handler)
    try:
        request = await publish_job()
        await asyncio.wait_for(handler.started.wait(), timeout=10)

        await worker.stop(grace_seconds=5)
    finally:
        serving.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serving
        await connection.close()

    body = await next_message("backend", RESULTS_QUEUE.name)
    assert body is not None
    result = envelope_type(Pong).model_validate_json(body)
    assert (result.payload.job_id, result.payload.text) == (request.job_id, "echo: Hi")
    assert await next_message("runner", JOBS_QUEUE.name, seconds=1) is None


async def test_a_job_that_outlasts_the_grace_period_is_left_for_redelivery() -> None:
    handler = EchoHandler(delay=30)
    worker, serving, connection = await worker_with(handler)
    try:
        request = await publish_job()
        await asyncio.wait_for(handler.started.wait(), timeout=10)

        await worker.stop(grace_seconds=0.2)
    finally:
        serving.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serving
        await connection.close()

    body = await next_message("runner", JOBS_QUEUE.name)
    assert body is not None
    assert envelope_type(Ping).model_validate_json(body).payload == request

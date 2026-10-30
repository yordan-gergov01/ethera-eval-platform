"""Publishing job requests to the real test broker over the backend's own connection.

Role: pins backend.messaging.publisher `JobPublisher`: a persistent message carrying the payload
  in its common_lib.messaging.envelope, with message id, correlation id and type set.
Used by: pytest (integration — needs the test database and broker).
Depends on: `empty_queues`, `backend_settings`, `broker_channel` from
  tests/integration/conftest.py; `Ping`/`ping` from tests/job_payloads.py.
Key invariants: runs on test-local payloads (docs/DECISIONS.md D-006); every payload field
  survives, not only the `JobPayload` base; no connection or an unroutable job is
  BROKER_UNAVAILABLE, never a silent loss; a payload never goes to a queue of another type.
"""

import asyncio

import pytest
from aio_pika.abc import AbstractRobustConnection

from backend.core.settings import BackendSettings
from backend.main import create_app
from backend.messaging.connection import BrokerConnection
from backend.messaging.publisher import JobPublisher
from common_lib.errors import ErrorCode, ServiceUnavailableError
from common_lib.messaging.envelope import envelope_type
from common_lib.messaging.jobs import MessageType
from common_lib.messaging.topology import JOBS_QUEUE, RESULTS_QUEUE
from tests.integration.conftest import broker_channel
from tests.job_payloads import Ping, ping

pytestmark = pytest.mark.usefixtures("empty_queues")


async def test_a_job_is_published_persistently_with_its_envelope(
    backend_settings: BackendSettings,
) -> None:
    request = ping("Hello there")
    app = create_app(backend_settings)
    async with app.router.lifespan_context(app):
        await app.state.broker.wait_until_connected()
        await JobPublisher(app.state.broker).publish(
            request, queue=JOBS_QUEUE, request_id="req-123"
        )

    async with broker_channel("runner") as channel:
        queue = await channel.get_queue(JOBS_QUEUE.name, ensure=False)
        message = await queue.get(fail=False)
        assert message is not None
        await message.ack()

    envelope = envelope_type(Ping).model_validate_json(message.body)
    # Every field of the payload class survives, not only the JobPayload base.
    assert envelope.payload == request
    assert (envelope.request_id, envelope.correlation_id) == ("req-123", request.job_id)
    assert message.content_type == "application/json"
    assert message.delivery_mode == 2
    assert message.message_id == str(envelope.message_id)
    assert message.correlation_id == str(request.job_id)
    assert message.type == MessageType.EVAL_TRIAL_BATCH_REQUESTED.value


async def test_publishing_without_a_broker_connection_is_broker_unavailable() -> None:
    publisher = JobPublisher(BrokerConnection(connect=_never_called))

    with pytest.raises(ServiceUnavailableError) as raised:
        await publisher.publish(ping(), queue=JOBS_QUEUE, request_id="req-1")

    assert raised.value.code is ErrorCode.BROKER_UNAVAILABLE


async def test_a_payload_is_never_published_to_a_queue_of_another_type() -> None:
    publisher = JobPublisher(BrokerConnection(connect=_never_called))

    with pytest.raises(ValueError, match="cannot be published"):
        await publisher.publish(ping(), queue=RESULTS_QUEUE, request_id="req-1")


async def test_an_unroutable_job_fails_instead_of_disappearing(
    backend_settings: BackendSettings,
) -> None:
    app = create_app(backend_settings)
    async with app.router.lifespan_context(app):
        connection = await app.state.broker.wait_until_connected()
        # The backend's configure permission also allows deleting the job queue.
        async with connection.channel() as channel:
            await (await channel.get_queue(JOBS_QUEUE.name, ensure=False)).delete(
                if_unused=False, if_empty=False
            )

        with pytest.raises(ServiceUnavailableError) as raised:
            await JobPublisher(app.state.broker).publish(
                ping(), queue=JOBS_QUEUE, request_id="req-2"
            )

    assert raised.value.code is ErrorCode.BROKER_UNAVAILABLE
    assert raised.value.__cause__ is not None


async def _never_called() -> AbstractRobustConnection:
    await asyncio.sleep(0)
    raise AssertionError("the publisher must not connect by itself")

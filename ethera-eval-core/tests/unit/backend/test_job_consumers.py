"""How the job consumers settle each message, with fake messages and a fake recorder.

Role: pins backend.messaging.consumers `JobConsumers`' settlement rules: a valid result is
  recorded and acked; an invalid result, a request on the result queue or a bug is rejected
  without requeue; an unreachable database requeues after a pause; a dead-lettered request
  fails its job; payload types must match their queues.
Used by: pytest (unit).
Depends on: `Ping`/`Pong`, `ping`, `pong_for` from tests/job_payloads.py; local fakes
  `FakeMessage`, `FakeRecorder`, `RecordingSleep`; a `BrokerConnection` that must never connect.
Key invariants: runs on test-local payloads (docs/DECISIONS.md D-006); the handlers are called
  directly, never through a broker; the pause is recorded, not slept.
"""

from typing import cast
from uuid import UUID

import pytest
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from backend.messaging.connection import BrokerConnection
from backend.messaging.consumers import JobConsumers
from common_lib.messaging.envelope import Envelope
from tests.job_payloads import Ping, Pong, ping, pong_for

JOB_ID = UUID("00000000-0000-4000-8000-0000000000aa")


class FakeMessage:
    def __init__(self, body: bytes, *, correlation_id: str | None = None) -> None:
        self.body = body
        self.correlation_id = correlation_id
        self.message_id = "m-1"
        self.outcome: str | None = None

    async def ack(self) -> None:
        self.outcome = "ack"

    async def nack(self, requeue: bool = True) -> None:
        self.outcome = f"nack(requeue={requeue})"

    async def reject(self, requeue: bool = False) -> None:
        self.outcome = f"reject(requeue={requeue})"


class FakeRecorder:
    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.results: list[Pong] = []
        self.undeliverable: list[UUID] = []

    async def record_result(self, result: Pong) -> bool:
        if self.error is not None:
            raise self.error
        self.results.append(result)
        return True

    async def fail_undeliverable(self, job_id: UUID) -> bool:
        if self.error is not None:
            raise self.error
        self.undeliverable.append(job_id)
        return True


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


async def never_connects() -> AbstractRobustConnection:
    raise AssertionError("the handlers must not connect")


def consumers(recorder: FakeRecorder, sleep: RecordingSleep | None = None) -> JobConsumers[Pong]:
    return JobConsumers(
        BrokerConnection(never_connects),
        recorder,
        result_type=Pong,
        request_type=Ping,
        prefetch_count=1,
        sleep=sleep or RecordingSleep(),
    )


def result_body() -> bytes:
    result = pong_for(ping("Hi", job_id=JOB_ID), "An answer")
    return Envelope[Pong].wrap(result, request_id="req-1").model_dump_json().encode()


def request_body() -> bytes:
    request = ping("Hi", job_id=JOB_ID)
    return Envelope[Ping].wrap(request, request_id="req-1").model_dump_json().encode()


def incoming(message: FakeMessage) -> AbstractIncomingMessage:
    return cast(AbstractIncomingMessage, message)


async def test_a_valid_result_is_recorded_and_acknowledged() -> None:
    recorder, message = FakeRecorder(), FakeMessage(result_body())

    await consumers(recorder).on_result(incoming(message))

    assert [(r.job_id, r.text) for r in recorder.results] == [(JOB_ID, "An answer")]
    assert message.outcome == "ack"


async def test_an_invalid_result_is_rejected_without_requeue() -> None:
    recorder, message = FakeRecorder(), FakeMessage(b'{"not": "an envelope"}')

    await consumers(recorder).on_result(incoming(message))

    assert recorder.results == []
    assert message.outcome == "reject(requeue=False)"


async def test_an_unreachable_database_requeues_after_a_pause() -> None:
    sleep = RecordingSleep()
    recorder, message = FakeRecorder(ConnectionRefusedError()), FakeMessage(result_body())

    await consumers(recorder, sleep).on_result(incoming(message))

    assert sleep.delays == [2.0]
    assert message.outcome == "nack(requeue=True)"


async def test_an_unexpected_error_dead_letters_the_result() -> None:
    recorder, message = FakeRecorder(RuntimeError("a bug")), FakeMessage(result_body())

    await consumers(recorder).on_result(incoming(message))

    assert message.outcome == "reject(requeue=False)"


@pytest.mark.parametrize(
    "message",
    [FakeMessage(request_body()), FakeMessage(b"garbage", correlation_id=str(JOB_ID))],
    ids=["valid request", "unreadable body with correlation id"],
)
async def test_a_dead_lettered_request_fails_its_job(message: FakeMessage) -> None:
    recorder = FakeRecorder()

    await consumers(recorder).on_dead_letter(incoming(message))

    assert recorder.undeliverable == [JOB_ID]
    assert message.outcome == "ack"


async def test_a_dead_letter_without_a_job_id_is_dropped() -> None:
    recorder, message = FakeRecorder(), FakeMessage(b"garbage")

    await consumers(recorder).on_dead_letter(incoming(message))

    assert recorder.undeliverable == []
    assert message.outcome == "reject(requeue=False)"


async def test_a_request_is_not_a_result() -> None:
    recorder, message = FakeRecorder(), FakeMessage(request_body())

    await consumers(recorder).on_result(incoming(message))

    assert recorder.results == []
    assert message.outcome == "reject(requeue=False)"


async def test_a_result_the_recorder_ignores_is_still_acknowledged() -> None:
    class IgnoringRecorder(FakeRecorder):
        async def record_result(self, result: Pong) -> bool:
            return False

    message = FakeMessage(result_body())

    await consumers(IgnoringRecorder()).on_result(incoming(message))

    assert message.outcome == "ack"


@pytest.mark.parametrize(
    ("result_type", "request_type"), [(Ping, Ping), (Pong, Pong)], ids=["result", "request"]
)
def test_payload_types_must_match_their_queues(
    result_type: type[Pong], request_type: type[Ping]
) -> None:
    with pytest.raises(ValueError, match="carries"):
        JobConsumers(
            BrokerConnection(never_connects),
            FakeRecorder(),
            result_type=result_type,
            request_type=request_type,
            prefetch_count=1,
        )

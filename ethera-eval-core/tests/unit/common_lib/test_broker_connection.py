"""Connecting to RabbitMQ: retried with exponential backoff until the broker answers.

Role: pins common_lib.messaging.connection `connect_with_retry`: the first attempt does not
  wait, refused or rejected connections are retried with capped exponential backoff and logged,
  other errors propagate, and the setup step runs before the connection is returned, again
  after every reconnect, with a refused setup closing the connection and retrying.
Used by: pytest (unit).
Depends on: local fakes `FlakyBroker`, `FakeConnection`, `RecordingSleep`, `RecordingSetup`; a
  `log_lines` fixture over common_lib.logging_config `configure_logging`. No broker.
Key invariants: the backoff is recorded, never slept; a bug (any non-connection error) is never
  swallowed as an outage.
"""

import io
import json
import logging
from collections.abc import Iterator
from typing import cast

import pytest
import structlog
from aio_pika.abc import AbstractRobustConnection
from aio_pika.exceptions import AMQPConnectionError, AMQPError

from common_lib.logging_config import configure_logging
from common_lib.messaging.connection import connect_with_retry


class FakeConnection:
    def __init__(self) -> None:
        self.reconnect_callbacks: set[object] = set()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FlakyBroker:
    """Refuses the first connections with the given errors, then accepts."""

    def __init__(self, *failures: Exception) -> None:
        self.failures = list(failures)
        self.attempts = 0
        self.connections: list[FakeConnection] = []

    @property
    def connection(self) -> FakeConnection:
        return self.connections[-1]

    async def connect(self) -> AbstractRobustConnection:
        self.attempts += 1
        if self.failures:
            raise self.failures.pop(0)
        self.connections.append(FakeConnection())
        return cast(AbstractRobustConnection, self.connection)


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging(service="test", stream=stream)
    yield stream
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def events(stream: io.StringIO, name: str) -> list[dict[str, object]]:
    return [e for e in map(json.loads, stream.getvalue().splitlines()) if e["event"] == name]


async def test_first_attempt_connects_without_waiting() -> None:
    broker, sleep = FlakyBroker(), RecordingSleep()

    connection = await connect_with_retry(broker.connect, sleep=sleep)

    assert connection is cast(AbstractRobustConnection, broker.connection)
    assert sleep.delays == []
    assert len(broker.connection.reconnect_callbacks) == 1


async def test_refused_and_rejected_connections_are_retried_with_backoff(
    log_lines: io.StringIO,
) -> None:
    broker = FlakyBroker(
        ConnectionRefusedError("refused"),
        AMQPConnectionError("ACCESS_REFUSED"),
        OSError("unreachable"),
    )
    sleep = RecordingSleep()

    await connect_with_retry(broker.connect, sleep=sleep)

    assert broker.attempts == 4
    assert sleep.delays == [1.0, 2.0, 4.0]
    failures = events(log_lines, "broker_unavailable")
    assert [f["error"] for f in failures] == [
        "ConnectionRefusedError",
        "AMQPConnectionError",
        "OSError",
    ]
    [connected] = events(log_lines, "broker_connected")
    assert connected["attempt"] == 4


async def test_backoff_is_capped() -> None:
    broker = FlakyBroker(*(ConnectionRefusedError() for _ in range(8)))
    sleep = RecordingSleep()

    await connect_with_retry(broker.connect, sleep=sleep, max_delay=30.0)

    assert sleep.delays == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0]


async def test_other_errors_are_not_swallowed() -> None:
    broker = FlakyBroker(ValueError("a bug, not an outage"))

    with pytest.raises(ValueError, match="a bug"):
        await connect_with_retry(broker.connect, sleep=RecordingSleep())


class RecordingSetup:
    """Declares nothing; refuses the first `failures` calls like a missing permission."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[object] = []

    async def __call__(self, connection: AbstractRobustConnection) -> None:
        self.calls.append(connection)
        if self.failures:
            self.failures -= 1
            raise AMQPError("ACCESS_REFUSED")


async def test_setup_runs_before_the_connection_is_returned() -> None:
    broker, setup = FlakyBroker(), RecordingSetup()

    connection = await connect_with_retry(broker.connect, setup=setup, sleep=RecordingSleep())

    assert setup.calls == [connection]
    # Logging, and the same setup again after every reconnect.
    assert len(broker.connection.reconnect_callbacks) == 2


async def test_a_refused_setup_closes_the_connection_and_is_retried(
    log_lines: io.StringIO,
) -> None:
    broker, setup, sleep = FlakyBroker(), RecordingSetup(failures=1), RecordingSleep()

    connection = await connect_with_retry(broker.connect, setup=setup, sleep=sleep)

    first, second = broker.connections
    assert first.closed
    assert not second.closed
    assert connection is cast(AbstractRobustConnection, second)
    assert sleep.delays == [1.0]
    [failure] = events(log_lines, "broker_unavailable")
    assert failure["error"] == "AMQPError"

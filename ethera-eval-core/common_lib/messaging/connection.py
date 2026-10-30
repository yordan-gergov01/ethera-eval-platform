"""Connecting to RabbitMQ: retried until the broker answers, then kept alive.

Role: `robust_connector` (one robust connection with the service's own user) and
  `connect_with_retry` (connect and run `setup`, retrying with exponential backoff).
Used by: `backend.main`, `backend.messaging.connection`, `runner.main`; the broker connection and
  runner tests.
Depends on: aio-pika's `RobustConnection`, `common_lib.settings.BrokerSettings`, structlog.
Key invariants: the first connection is retried, so a service can start before the broker;
  refused connections, rejected credentials and refused declarations are all retried and logged
  with their type. A connection is returned only after `setup` has run, and `setup` runs again
  after each reconnect, so callers never see a connection without its queues. A failed first
  attempt is closed explicitly, otherwise aio-pika's reconnect task would keep shutdown from
  ending. ORM-free (import-linter).
"""

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from aio_pika import RobustConnection
from aio_pika.abc import AbstractRobustConnection
from aio_pika.connection import make_url
from aio_pika.exceptions import AMQPError

from common_lib.settings import BrokerSettings

logger = structlog.get_logger(__name__)

INITIAL_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 30.0

Connector = Callable[[], Awaitable[AbstractRobustConnection]]
# Runs on a fresh connection before it is handed out, and again after each reconnect.
Setup = Callable[[AbstractRobustConnection], Awaitable[None]]
Sleep = Callable[[float], Awaitable[None]]


def robust_connector(settings: BrokerSettings, *, connection_name: str) -> Connector:
    """A function that opens one robust connection with the service's own user."""

    async def connect() -> AbstractRobustConnection:
        connection = RobustConnection(
            make_url(
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                login=settings.rabbitmq_user,
                password=settings.rabbitmq_password.get_secret_value(),
                virtualhost=settings.rabbitmq_vhost,
            ),
            # Shown in the broker's management view, to tell the services apart.
            client_properties={"connection_name": connection_name},
        )
        try:
            await connection.connect()
        except BaseException:
            # A failed or cancelled first attempt leaves aio-pika's background reconnect
            # task running, and that task ignores cancellation until the connection is
            # closed: without this, shutting down while the broker is down never ends.
            await connection.close()
            raise
        return connection

    return connect


async def connect_with_retry(
    connect: Connector,
    *,
    setup: Setup | None = None,
    initial_delay: float = INITIAL_RETRY_DELAY_SECONDS,
    max_delay: float = MAX_RETRY_DELAY_SECONDS,
    sleep: Sleep = asyncio.sleep,
) -> AbstractRobustConnection:
    """Connect and run `setup`, retrying with exponential backoff until both succeed.

    Refused connections, rejected credentials and refused declarations are all
    retried: the broker may still be starting, and its users are provisioned at
    boot. Each failure is logged with its type, so a wrong password or a missing
    permission shows up in the logs. The connection is returned only after `setup`
    has run, so callers never see a connection without its queues.
    """
    delay = initial_delay
    attempt = 1
    while True:
        try:
            connection = await _connect_and_set_up(connect, setup)
            break
        except (AMQPError, OSError) as exc:
            logger.warning(
                "broker_unavailable",
                attempt=attempt,
                retry_in_seconds=delay,
                error=type(exc).__name__,
            )
            await sleep(delay)
            delay = min(delay * 2, max_delay)
            attempt += 1

    logger.info("broker_connected", attempt=attempt)
    connection.reconnect_callbacks.add(_log_reconnected)
    if setup is not None:
        set_up = setup

        async def set_up_again(_: object) -> None:
            # A broker that lost its data on restart gets its queues back.
            await set_up(connection)

        connection.reconnect_callbacks.add(set_up_again)
    return connection


async def _connect_and_set_up(connect: Connector, setup: Setup | None) -> AbstractRobustConnection:
    connection = await connect()
    if setup is None:
        return connection
    try:
        await setup(connection)
    except BaseException:
        # Do not leave a half-prepared connection reconnecting in the background.
        await connection.close()
        raise
    return connection


def _log_reconnected(_: object) -> None:
    logger.info("broker_reconnected")

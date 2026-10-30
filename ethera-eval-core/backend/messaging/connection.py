"""The backend's connection to RabbitMQ, established in the background.

Role: `BrokerConnection` connects (and keeps reconnecting) in a background task;
  `declare_backend_topology` declares what the backend publishes to or consumes from.
Used by: `backend.main` (started in the lifespan, kept on `app.state.broker`);
  `backend.messaging.publisher` and `backend.messaging.consumers`.
Depends on: `common_lib.messaging.connection` (`connect_with_retry`),
  `common_lib.messaging.declare`, `common_lib.messaging.topology`, aio-pika.
Key invariants: the backend serves every request that does not need the broker while it is
  unreachable — the connection never blocks startup, and features that need it check
  `connection` first. The connection is published only once the topology exists, and the
  backend declares the runner's job queue too, so a job published before the runner first
  starts waits instead of being dropped as unroutable (template_core D-010). Waiting for the
  connection is shielded, so a caller that gives up does not cancel the connecting.
"""

import asyncio
import contextlib

import structlog
from aio_pika.abc import AbstractRobustConnection

from common_lib.messaging.connection import Connector, connect_with_retry
from common_lib.messaging.declare import declare_topology
from common_lib.messaging.topology import JOBS_QUEUE, RESULTS_QUEUE

logger = structlog.get_logger(__name__)


async def declare_backend_topology(connection: AbstractRobustConnection) -> None:
    """Declare everything the backend publishes to or consumes from.

    That includes the job queue, which the runner consumes: jobs published before
    the runner has ever started then wait in the queue instead of being dropped by
    the broker as unroutable.
    """
    async with connection.channel() as channel:
        await declare_topology(channel, (JOBS_QUEUE, RESULTS_QUEUE))


class BrokerConnection:
    def __init__(self, connect: Connector) -> None:
        self._connect = connect
        self._connection: AbstractRobustConnection | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def connection(self) -> AbstractRobustConnection | None:
        """The open connection with its topology declared, or None until then."""
        return self._connection

    def start(self) -> None:
        """Start connecting in the background; returns immediately."""
        self._task = asyncio.create_task(self._run(), name="broker_connect")

    async def wait_until_connected(self) -> AbstractRobustConnection:
        """Wait for the background connection to be established."""
        if self._task is None:
            raise RuntimeError("start() must be called first")
        # Shielded: a caller that gives up waiting must not cancel the connecting.
        await asyncio.shield(self._task)
        if self._connection is None:
            raise RuntimeError("the connect task ended without a connection")
        return self._connection

    async def close(self) -> None:
        """Stop connecting, or close the connection if it is open."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._connection is not None:
            await self._connection.close()
            logger.info("broker_connection_closed")

    async def _run(self) -> None:
        # Published only once the topology exists, so no message can go unroutable.
        self._connection = await connect_with_retry(self._connect, setup=declare_backend_topology)

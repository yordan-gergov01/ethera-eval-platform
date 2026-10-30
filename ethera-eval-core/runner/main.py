"""The runner process: `python -m runner.main`.

Role: a plain asyncio process without a web framework or ports: it connects to RabbitMQ as its
  own user (retrying until the broker answers), declares its queues, and keeps the heartbeat file
  fresh while connected. SIGTERM or SIGINT stops it: the connection is closed and it exits.
Used by: the runner image's CMD (`runner/Dockerfile`); tests/integration/test_runner_lifecycle.py.
Depends on: `common_lib.messaging.connection`, `common_lib.logging_config`, `common_lib.settings`,
  `runner.settings`, `runner.heartbeat`, `runner.worker.declare_runner_topology`.
Key invariants: it serves no job handler yet — `JobWorker` is wired in slice 003 (D-006). A stop
  while still connecting cancels the connecting instead of waiting for the broker.
"""

import asyncio
import contextlib
import signal

import structlog
from aio_pika.abc import AbstractRobustConnection

from common_lib.logging_config import configure_logging
from common_lib.messaging.connection import connect_with_retry, robust_connector
from common_lib.settings import load_settings
from runner.heartbeat import Heartbeat
from runner.settings import RunnerSettings
from runner.worker import declare_runner_topology

SERVICE_NAME = "runner"

logger = structlog.get_logger(__name__)


async def run(settings: RunnerSettings, stop: asyncio.Event) -> None:
    """Stay connected until `stop` is set, then shut down."""
    connection: AbstractRobustConnection | None = None

    def connected() -> bool:
        return connection is not None and not connection.is_closed

    heartbeat = asyncio.create_task(Heartbeat(connected).run(), name="heartbeat")
    logger.info("startup_complete")
    try:
        connecting = asyncio.create_task(
            connect_with_retry(
                robust_connector(settings, connection_name=SERVICE_NAME),
                setup=declare_runner_topology,
            )
        )
        stopping = asyncio.create_task(stop.wait())
        await asyncio.wait({connecting, stopping}, return_when=asyncio.FIRST_COMPLETED)
        if connecting.done():
            connection = connecting.result()
            # JobWorker.serve(connection), then JobWorker.stop(grace) on shutdown:
            # Wired in slice 003 (EvalTrialBatchRequested); see docs/DECISIONS.md D-006.
            await stopping
        else:
            connecting.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connecting
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
        if connection is not None:
            await connection.close()
        logger.info("shutdown_complete")


async def _main() -> None:
    settings = load_settings(RunnerSettings)
    configure_logging(
        service=SERVICE_NAME, level=settings.log_level, log_format=settings.log_format
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(stop_signal, stop.set)
    await run(settings, stop)


if __name__ == "__main__":
    asyncio.run(_main())

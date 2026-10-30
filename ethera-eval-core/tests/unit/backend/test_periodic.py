"""Periodic background tasks: they repeat, survive failures and stop with the block.

Role: pins backend.core.periodic `periodic_task`: the action repeats until the block exits, the
  task is gone afterwards, and a failing run is logged as `periodic_task_failed` without
  stopping the task.
Used by: pytest (unit).
Depends on: the local `log_lines` fixture over common_lib.logging_config `configure_logging`.
  No services.
Key invariants: real asyncio timing with short intervals; no task named after the action
  survives the block.
"""

import asyncio
import io
import json
import logging
from collections.abc import Iterator

import pytest
import structlog

from backend.core.periodic import periodic_task
from common_lib.logging_config import configure_logging


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging(service="test", stream=stream)
    yield stream
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


async def test_action_repeats_until_the_block_exits() -> None:
    runs = 0

    async def action() -> None:
        nonlocal runs
        runs += 1

    async with periodic_task("counter", interval_seconds=0.01, action=action):
        await asyncio.sleep(0.1)
    finished = runs
    await asyncio.sleep(0.05)

    assert finished >= 3
    assert runs == finished
    assert not [t for t in asyncio.all_tasks() if t.get_name() == "counter"]


async def test_a_failing_run_is_logged_and_the_task_continues(log_lines: io.StringIO) -> None:
    runs = 0

    async def flaky() -> None:
        nonlocal runs
        runs += 1
        if runs == 1:
            raise ConnectionRefusedError("database briefly unreachable")

    async with periodic_task("flaky", interval_seconds=0.01, action=flaky):
        await asyncio.sleep(0.1)

    assert runs >= 3
    [failure] = [
        e
        for e in map(json.loads, log_lines.getvalue().splitlines())
        if e["event"] == "periodic_task_failed"
    ]
    assert failure["task"] == "flaky"
    assert failure["level"] == "error"
    assert "ConnectionRefusedError" in json.dumps(failure["exception"])

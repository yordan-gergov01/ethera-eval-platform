"""The heartbeat file: written only while connected, judged by its age.

Role: pins runner.heartbeat `Heartbeat` and `is_fresh`: the file is written while connected,
  never while disconnected, and an old file is not fresh.
Used by: pytest (unit).
Depends on: pytest's `tmp_path`; the autouse `_required_environment` from
  tests/unit/runner/conftest.py. No broker.
Key invariants: "connected" is a plain callable, so no broker is involved; the age is set with
  `os.utime`, never by waiting.
"""

import asyncio
import contextlib
import os
import time
from pathlib import Path

from runner.heartbeat import Heartbeat, is_fresh


async def beat_for(heartbeat: Heartbeat, seconds: float) -> None:
    task = asyncio.create_task(heartbeat.run())
    await asyncio.sleep(seconds)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_the_file_is_written_while_connected(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat"

    await beat_for(Heartbeat(lambda: True, path=path, interval_seconds=0.01), 0.1)

    assert is_fresh(path)


async def test_nothing_is_written_while_disconnected(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat"

    await beat_for(Heartbeat(lambda: False, path=path, interval_seconds=0.01), 0.1)

    assert not path.exists()
    assert not is_fresh(path)


def test_an_old_heartbeat_is_not_fresh(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat"
    path.write_text("old")
    an_hour_ago = time.time() - 3600
    os.utime(path, (an_hour_ago, an_hour_ago))

    assert not is_fresh(path, max_age_seconds=30)
    assert is_fresh(path, max_age_seconds=7200)

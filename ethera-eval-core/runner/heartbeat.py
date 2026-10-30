"""Liveness of the runner as a file, for the container health check.

Role: `Heartbeat` rewrites a file every few seconds while the runner is healthy;
  `python -m runner.heartbeat` reports unhealthy when the file is missing or too old.
Used by: `runner.main` (the heartbeat task); the runner's compose health check
  (`python -m runner.heartbeat`); tests/unit/runner/test_heartbeat.py.
Depends on: the standard library only.
Key invariants: the service has no ports, so the health check cannot ask it anything — the file
  is the only signal. It beats only while connected to the broker. Several missed beats are
  tolerated, so a short pause does not flap the health status. The file lives in a private tmpfs.
"""

import asyncio
import sys
import time
from collections.abc import Callable
from pathlib import Path

HEARTBEAT_FILE = Path("/tmp/runner-heartbeat")  # noqa: S108 - a private tmpfs in the container
INTERVAL_SECONDS = 5.0
# Several missed beats, so a short pause does not flap the health status.
MAX_AGE_SECONDS = 30.0


class Heartbeat:
    def __init__(
        self,
        is_healthy: Callable[[], bool],
        *,
        path: Path = HEARTBEAT_FILE,
        interval_seconds: float = INTERVAL_SECONDS,
    ) -> None:
        self._is_healthy = is_healthy
        self._path = path
        self._interval = interval_seconds

    async def run(self) -> None:
        """Beat while healthy, until cancelled."""
        while True:
            if self._is_healthy():
                await asyncio.to_thread(self._path.write_text, str(time.time()))
            await asyncio.sleep(self._interval)


def is_fresh(path: Path = HEARTBEAT_FILE, *, max_age_seconds: float = MAX_AGE_SECONDS) -> bool:
    """Whether the heartbeat file exists and was written recently."""
    try:
        age = time.time() - path.stat().st_mtime
    except FileNotFoundError:
        return False
    return age <= max_age_seconds


if __name__ == "__main__":
    sys.exit(0 if is_fresh() else 1)

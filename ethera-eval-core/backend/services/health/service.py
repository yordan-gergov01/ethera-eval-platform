"""Service health: is the backend able to serve requests?

Role: `HealthService.database_ok` and `build_health_service`, which wires it to `DatabaseProbe`.
Used by: `backend.services.health` (re-export), and through it `backend.api.health`.
Depends on: `backend.dal.health.DatabaseProbe` (behind the `DatabasePing` Protocol), structlog.
Key invariants: any failure of the ping means "not healthy" (a broad `except` on purpose); the
  reason goes to the logs, never to the response.
"""

from typing import Protocol

import structlog

from backend.dal.health import DatabaseProbe

logger = structlog.get_logger(__name__)


class DatabasePing(Protocol):
    async def ping(self) -> None: ...


class HealthService:
    """Reports whether the backend's dependencies are reachable."""

    def __init__(self, database: DatabasePing) -> None:
        self._database = database

    async def database_ok(self) -> bool:
        try:
            await self._database.ping()
        except Exception:
            # Any failure means "not healthy"; the reason belongs in the logs.
            logger.warning("health_database_unreachable", exc_info=True)
            return False
        return True


def build_health_service() -> HealthService:
    """Wire the service to its real collaborators."""
    return HealthService(database=DatabaseProbe())

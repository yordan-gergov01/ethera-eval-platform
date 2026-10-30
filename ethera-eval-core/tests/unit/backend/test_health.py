"""`GET /health`: 200 when the database answers, 503 otherwise.

Role: pins backend.services.health `HealthService` behind /health in `backend.main.create_app`:
  ok/ok or unavailable/unavailable, a warning logged when the database does not answer, no
  access-log line per health check, and /health outside the versioned API.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; a local
  `FakeDatabase` swapped in through the `build_health_service` dependency override.
Key invariants: the only fake is the database ping at the boundary; the rest of the app is real.
"""

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.settings import BackendSettings
from backend.main import create_app
from backend.services.health import HealthService, build_health_service


class FakeDatabase:
    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable

    async def ping(self) -> None:
        if not self.reachable:
            raise ConnectionRefusedError("database is down")


def app_with_database(reachable: bool) -> FastAPI:
    app = create_app(BackendSettings())
    app.dependency_overrides[build_health_service] = lambda: HealthService(FakeDatabase(reachable))
    return app


async def test_healthy_when_the_database_answers() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_with_database(reachable=True)), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_unavailable_when_the_database_does_not_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = app_with_database(reachable=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    [warning] = [line for line in lines if line["event"] == "health_database_unreachable"]
    assert warning["level"] == "warning"
    assert warning["exception"][0]["exc_type"] == "ConnectionRefusedError"


async def test_health_checks_do_not_flood_the_access_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = app_with_database(reachable=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/health")

    events = [json.loads(line)["event"] for line in capsys.readouterr().out.splitlines()]
    assert "request" not in events


def test_health_is_outside_the_versioned_api() -> None:
    paths = app_with_database(reachable=True).openapi()["paths"]

    assert "/health" in paths
    assert not any(path.startswith("/api/v1") and "health" in path for path in paths)

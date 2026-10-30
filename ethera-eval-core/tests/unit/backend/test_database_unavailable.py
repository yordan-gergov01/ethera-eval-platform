"""Global handling of an unreachable database: 503 everywhere, real bugs stay 500.

Role: pins backend.api.errors' database-unavailable handler as `backend.main.create_app` wires
  it: every driver error meaning "unreachable" is a 503 DATABASE_UNAVAILABLE problem with
  Retry-After and CORS headers, logged once with its traceback; other failures stay 500.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; a probe
  route that raises asyncpg, Tortoise and socket errors as the driver would. No services.
Key invariants: no database is involved, the errors are raised directly; driver details never
  reach the response; a query error or a bug is never disguised as unavailability.
"""

import json
import socket
from collections.abc import Callable

import pytest
from asyncpg import exceptions as pg
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise.exceptions import DBConnectionError, OperationalError

from backend.core.settings import BackendSettings
from backend.main import create_app

FRONTEND = "http://localhost:3000"

UNAVAILABLE: dict[str, Callable[[], Exception]] = {
    "connection refused": lambda: ConnectionRefusedError("[Errno 111] Connection refused"),
    "connection lost": lambda: pg.ConnectionDoesNotExistError("connection was closed"),
    "server shutting down": lambda: pg.AdminShutdownError("terminating connection"),
    "server starting": lambda: pg.CannotConnectNowError("the database system is starting up"),
    "too many connections": lambda: pg.TooManyConnectionsError("too many clients"),
    "tortoise connection error": lambda: DBConnectionError("cannot connect"),
    "host unresolvable": lambda: socket.gaierror(-2, "Name or service not known"),
    "connect timeout": lambda: TimeoutError("timed out"),
}


def build_app(error: Callable[[], Exception]) -> FastAPI:
    app = create_app(BackendSettings())

    @app.get("/api/v1/probe")
    async def probe() -> None:
        # Raised from deep inside a request, as the driver would.
        raise error()

    return app


async def call(app: FastAPI) -> tuple[int, dict[str, object], dict[str, str]]:
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/probe", headers={"Origin": FRONTEND})
    return response.status_code, response.json(), dict(response.headers)


@pytest.mark.parametrize("case", list(UNAVAILABLE))
async def test_unreachable_database_is_503_problem_details(case: str) -> None:
    status, body, headers = await call(build_app(UNAVAILABLE[case]))

    assert status == 503
    assert headers["content-type"] == "application/problem+json"
    assert body["code"] == "DATABASE_UNAVAILABLE"
    assert body["request_id"] == headers["x-request-id"]
    assert headers["retry-after"] == "5"
    # Readable by the browser like every other error, including when to retry.
    assert headers["access-control-allow-origin"] == FRONTEND
    assert "retry-after" in headers["access-control-expose-headers"].lower()


async def test_driver_details_stay_out_of_the_response() -> None:
    _, body, _ = await call(build_app(UNAVAILABLE["connection refused"]))

    assert "Errno" not in json.dumps(body)
    assert "111" not in str(body["detail"])


async def test_unavailability_is_logged_once_with_its_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = build_app(UNAVAILABLE["connection lost"])
    await call(app)

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    [logged] = [line for line in lines if line["event"] == "database_unavailable"]
    assert logged["level"] == "error"
    assert logged["exception"][0]["exc_type"] == "ConnectionDoesNotExistError"
    assert not [line for line in lines if line["event"] == "unhandled_exception"]


@pytest.mark.parametrize(
    "error",
    [
        lambda: OperationalError('relation "users" does not exist'),
        lambda: pg.QueryCanceledError("canceling statement due to statement timeout"),
        lambda: ValueError("a bug"),
    ],
)
async def test_other_failures_remain_internal_errors(error: Callable[[], Exception]) -> None:
    status, body, _ = await call(build_app(error))

    assert status == 500
    assert body["code"] == "INTERNAL_ERROR"

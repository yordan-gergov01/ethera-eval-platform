"""The request middleware never writes raw paths or exception text into the technical logs.

Role: seals FIX-003 on backend.api.middleware as installed by `backend.main.create_app`: the
  `unhandled_exception` line and the access line name the route template (or no path when no
  route matched) and the exception by its type names only.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; a test
  route `/api/v1/things/{thing_id}` added to the app; the real logging pipeline, captured with
  `capsys`. No services.
Key invariants: `test_unhandled_errors_log_neither_raw_paths_nor_exception_text` plants an ID in
  the path and a value in the exception chain's messages (as asyncpg renders a bound parameter
  into its message) and proves both absent while the lines that would carry them were captured
  (anti-vacuity).
"""

import json
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.settings import BackendSettings
from backend.main import create_app

PATH_ID = "pathzq91id"
UNMATCHED_ID = "unmatchedzq92id"
BOUND_VALUE = "boundzq93value"
ROUTE_TEMPLATE = "/api/v1/things/{thing_id}"


def build_app() -> FastAPI:
    app = create_app(BackendSettings())

    @app.get(ROUTE_TEMPLATE)
    async def read_thing(thing_id: str) -> None:
        try:
            raise ValueError(f"invalid input for query argument $1: {BOUND_VALUE}")
        except ValueError as exc:
            raise RuntimeError(f"query for {thing_id} failed: {BOUND_VALUE}") from exc

    return app


def _lines(output: str) -> list[dict[str, Any]]:  # Any: JSON log values
    return [json.loads(line) for line in output.splitlines()]


async def test_unhandled_errors_log_neither_raw_paths_nor_exception_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Build the app inside the test so its log handler writes to the captured stdout.
    app = build_app()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        failed = await client.get(f"/api/v1/things/{PATH_ID}")
        unmatched = await client.get(f"/api/v1/no-such-route/{UNMATCHED_ID}")
    output = capsys.readouterr().out

    assert failed.status_code == 500
    assert unmatched.status_code == 404
    lines = _lines(output)
    # Anti-vacuity: the failure and both access lines were logged through the real handler.
    [failure] = [line for line in lines if line["event"] == "unhandled_exception"]
    assert failure["error_type"] == "RuntimeError"
    assert failure["error_chain"] == ["RuntimeError", "ValueError"]
    assert failure["path"] == ROUTE_TEMPLATE
    access = [line for line in lines if line["event"] == "request"]
    assert [line["status"] for line in access] == [500, 404]
    assert access[0]["path"] == ROUTE_TEMPLATE
    assert "path" not in access[1]

    leaked = [value for value in (PATH_ID, UNMATCHED_ID, BOUND_VALUE) if value in output]
    assert leaked == [], output

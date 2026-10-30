"""Application factory: request IDs, access logging, CORS, and the docs toggle.

Role: pins the cross-cutting behaviour `backend.main.create_app` installs: an X-Request-ID
  generated or validated and reused, one JSON access line per request, CORS for the configured
  origin with the headers clients read exposed, and API docs that can be switched off.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; a `/ping`
  route added to the app per test; httpx `ASGITransport`. No services.
Key invariants: drives the real app in process without running its lifespan, so nothing
  connects; the app is built inside a test that reads logs, so its handler writes to the
  captured stdout; CORS never allows credentials or foreign origins.
"""

import json
import re
from collections.abc import AsyncIterator, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.settings import BackendSettings
from backend.main import create_app

FRONTEND = "http://localhost:3000"
AppFactory = Callable[..., FastAPI]


@pytest.fixture
def make_app() -> AppFactory:
    def factory(**overrides: object) -> FastAPI:
        app = create_app(BackendSettings.model_validate(overrides))

        @app.get("/ping")
        async def ping() -> dict[str, str]:
            return {"pong": "ok"}

        return app

    return factory


@pytest.fixture
async def client(make_app: AppFactory) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=make_app()), base_url="http://test") as c:
        yield c


async def test_request_id_is_generated_and_returned(client: AsyncClient) -> None:
    response = await client.get("/ping")

    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


async def test_valid_incoming_request_id_is_reused(client: AsyncClient) -> None:
    response = await client.get("/ping", headers={"X-Request-ID": "frontend-abc.123"})

    assert response.headers["x-request-id"] == "frontend-abc.123"


async def test_invalid_incoming_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/ping", headers={"X-Request-ID": "bad id with spaces"})

    assert response.headers["x-request-id"] != "bad id with spaces"
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


async def test_one_access_line_per_request(
    make_app: AppFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    # Build the app inside the test so its log handler writes to the captured stdout.
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ping", headers={"X-Request-ID": "req-1"})

    access = [
        line
        for line in map(json.loads, capsys.readouterr().out.splitlines())
        if line["event"] == "request"
    ]
    assert len(access) == 1
    [line] = access
    assert line["method"] == "GET"
    assert line["path"] == "/ping"
    assert line["status"] == response.status_code
    assert line["request_id"] == "req-1"
    assert line["service"] == "backend"
    assert isinstance(line["duration_ms"], float)


async def test_docs_are_served_when_enabled(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200


async def test_docs_can_be_switched_off(make_app: AppFactory) -> None:
    app = make_app(enable_api_docs=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/docs")).status_code == 404
        assert (await c.get("/openapi.json")).status_code == 404


async def test_cors_allows_the_configured_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/ping",
        headers={
            "Origin": FRONTEND,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert "access-control-allow-credentials" not in response.headers


async def test_cors_exposes_the_headers_clients_read(client: AsyncClient) -> None:
    response = await client.get("/ping", headers={"Origin": FRONTEND})

    assert response.headers["access-control-allow-origin"] == FRONTEND
    exposed = {h.strip() for h in response.headers["access-control-expose-headers"].split(",")}
    assert {"x-request-id", "retry-after", "location"} <= {h.lower() for h in exposed}


async def test_cors_ignores_other_origins(client: AsyncClient) -> None:
    response = await client.get("/ping", headers={"Origin": "https://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers

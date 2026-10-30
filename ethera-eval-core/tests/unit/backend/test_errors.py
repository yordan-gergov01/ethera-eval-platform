"""Every error is RFC 9457 problem details with a stable code and the request ID.

Role: pins backend.api.errors as installed by `backend.main.create_app`: each
  common_lib.errors `AppError` maps to its status and code, plus 401, 429, 404, 405, 400, 413,
  validation and unexpected-exception responses, all readable by the browser through CORS.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; test
  routes added to the app (`/raise/{kind}`, `/items`, `/boom`). No services.
Key invariants: validation errors list fields without echoing the input; a 500 is generic and
  logs the full exception chain with the request ID; every `ErrorCode` value equals its name,
  since the values are part of the API.
"""

import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pydantic import BaseModel, Field

from backend.core.settings import BackendSettings
from backend.main import create_app
from common_lib.errors import (
    AppError,
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    PermissionDeniedError,
    RateLimitExceededError,
    ServiceUnavailableError,
)

MAX_BODY = 2048
INTERNAL_DETAIL = "connection to db-internal-host:5432 refused"
FRONTEND = "http://localhost:3000"


class Item(BaseModel):
    name: str = Field(min_length=3)
    password: str = Field(min_length=12)


ERRORS: dict[str, AppError] = {
    "auth": AuthenticationError(),
    "forbidden": PermissionDeniedError(),
    "missing": NotFoundError("User not found."),
    "conflict": ConflictError("Username is taken."),
    "rule": BusinessRuleError("You cannot change your own role."),
    "limited": RateLimitExceededError(retry_after_seconds=17),
    "unavailable": ServiceUnavailableError(),
    # A more specific code from the catalogue overrides the default one.
    "overridden": ConflictError("Already done.", code=ErrorCode.BUSINESS_RULE_VIOLATION),
}


def build_app() -> FastAPI:
    app = create_app(BackendSettings(max_request_body_bytes=MAX_BODY))

    @app.get("/raise/{kind}")
    async def raise_error(kind: str) -> None:
        raise ERRORS[kind]

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, str]:
        return {"name": item.name}

    @app.get("/boom")
    async def boom() -> None:
        try:
            raise ConnectionRefusedError(INTERNAL_DETAIL)
        except ConnectionRefusedError as exc:
            raise RuntimeError("failed to load data") from exc

    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://test") as c:
        yield c


def problem(response: Response) -> dict[str, object]:
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, object] = response.json()
    assert body["type"] == "about:blank"
    assert body["status"] == response.status_code
    assert body["request_id"] == response.headers["x-request-id"]
    assert isinstance(body["title"], str)
    assert isinstance(body["detail"], str)
    return body


@pytest.mark.parametrize(
    ("kind", "status", "code"),
    [
        ("auth", 401, ErrorCode.AUTHENTICATION_FAILED),
        ("forbidden", 403, ErrorCode.PERMISSION_DENIED),
        ("missing", 404, ErrorCode.NOT_FOUND),
        ("conflict", 409, ErrorCode.CONFLICT),
        ("rule", 422, ErrorCode.BUSINESS_RULE_VIOLATION),
        ("limited", 429, ErrorCode.RATE_LIMITED),
        ("unavailable", 503, ErrorCode.SERVICE_UNAVAILABLE),
        ("overridden", 409, ErrorCode.BUSINESS_RULE_VIOLATION),
    ],
)
async def test_application_errors_map_to_status_and_code(
    client: AsyncClient, kind: str, status: int, code: ErrorCode
) -> None:
    response = await client.get(f"/raise/{kind}")

    assert response.status_code == status
    body = problem(response)
    assert body["code"] == code
    assert body["instance"] == f"/raise/{kind}"
    assert body["detail"] == ERRORS[kind].message


async def test_401_tells_the_client_to_use_a_bearer_token(client: AsyncClient) -> None:
    response = await client.get("/raise/auth")

    assert response.headers["www-authenticate"] == "Bearer"


async def test_429_says_when_to_retry(client: AsyncClient) -> None:
    response = await client.get("/raise/limited")

    assert response.headers["retry-after"] == "17"


async def test_unknown_route_is_problem_details(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert problem(response)["code"] == "NOT_FOUND"


async def test_wrong_method_is_problem_details(client: AsyncClient) -> None:
    response = await client.delete("/items")

    assert response.status_code == 405
    assert problem(response)["code"] == "METHOD_NOT_ALLOWED"
    assert "POST" in response.headers["allow"]


async def test_schema_violations_list_fields_without_echoing_input(client: AsyncClient) -> None:
    response = await client.post("/items", json={"name": "ab", "password": "short-secret"[:8]})

    assert response.status_code == 422
    body = problem(response)
    assert body["code"] == "VALIDATION_FAILED"
    errors = body["errors"]
    assert isinstance(errors, list)
    assert {error["field"] for error in errors} == {"body.name", "body.password"}
    assert all(set(error) == {"field", "message", "type"} for error in errors)
    assert "short-se" not in response.text


async def test_unparseable_json_is_400(client: AsyncClient) -> None:
    response = await client.post(
        "/items", content=b'{"name": "abc",', headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    body = problem(response)
    assert body["code"] == "MALFORMED_REQUEST"
    assert "errors" not in body


async def test_declared_oversized_body_is_413(client: AsyncClient) -> None:
    response = await client.post(
        "/items", content=b"x" * (MAX_BODY + 1), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert problem(response)["code"] == "PAYLOAD_TOO_LARGE"


async def test_streamed_oversized_body_is_413(client: AsyncClient) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(4):
            yield b"x" * 1024

    response = await client.post(
        "/items", content=chunks(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert problem(response)["code"] == "PAYLOAD_TOO_LARGE"


async def test_unexpected_exception_is_generic_500_and_logged_with_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Build the app inside the test so its log handler writes to the captured stdout.
    app = build_app()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    body = problem(response)
    assert body["code"] == "INTERNAL_ERROR"
    assert INTERNAL_DETAIL not in response.text
    assert "RuntimeError" not in response.text

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    [failure] = [line for line in lines if line["event"] == "unhandled_exception"]
    assert failure["request_id"] == body["request_id"]
    assert failure["path"] == "/boom"
    # The full chain is logged: the RuntimeError and the error that caused it.
    exc_types = {frame["exc_type"] for frame in failure["exception"]}
    assert exc_types == {"RuntimeError", "ConnectionRefusedError"}
    [access] = [line for line in lines if line["event"] == "request"]
    assert access["status"] == 500


# --- A browser must be able to read every error ----------------------------------------


async def _oversized_stream() -> AsyncIterator[bytes]:
    for _ in range(4):
        yield b"x" * 1024


async def _send(case: str, client: AsyncClient) -> Response:
    headers = {"Origin": FRONTEND, "Content-Type": "application/json"}
    if case == "unexpected exception":
        return await client.get("/boom", headers=headers)
    if case == "unknown route":
        return await client.get("/does-not-exist", headers=headers)
    if case == "declared oversized body":
        return await client.post("/items", content=b"x" * (MAX_BODY + 1), headers=headers)
    # Fails inside body parsing rather than before the body is read.
    return await client.post("/items", content=_oversized_stream(), headers=headers)


@pytest.mark.parametrize(
    ("case", "status"),
    [
        ("unexpected exception", 500),
        ("unknown route", 404),
        ("declared oversized body", 413),
        ("streamed oversized body", 413),
    ],
)
async def test_error_responses_carry_cors_headers_for_the_allowed_origin(
    case: str, status: int
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=build_app(), raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await _send(case, client)

    assert response.status_code == status
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
    assert problem(response)["request_id"] == response.headers["x-request-id"]


def test_error_codes_are_their_own_names() -> None:
    # The values are part of the API; a member whose value drifts from its name is a typo.
    assert all(code.value == code.name for code in ErrorCode)

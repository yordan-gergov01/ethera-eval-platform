"""The API documentation marks exactly the protected operations as needing a token.

Role: pins the OpenAPI security requirements produced by `backend.main.create_app` (only login
  is open) and that backend.api.dependencies.rate_limit `bearer_token` reads the Authorization
  header exactly like backend.api.dependencies.auth `oauth2_scheme`.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; bare
  Starlette `Request` objects. No services.
Key invariants: every /api/v1 operation except login keeps its security requirement, so a new
  route cannot silently appear unprotected in the docs.
"""

import pytest
from fastapi import Request

from backend.api.dependencies.auth import oauth2_scheme
from backend.api.dependencies.rate_limit import bearer_token
from backend.core.settings import BackendSettings
from backend.main import create_app

LOGIN = ("post", "/api/v1/auth/login")


def operations() -> dict[tuple[str, str], dict[str, object]]:
    schema = create_app(BackendSettings.model_validate({})).openapi()
    return {
        (method, path): operation
        for path, methods in schema["paths"].items()
        if path.startswith("/api/v1/")
        for method, operation in methods.items()
    }


def test_login_needs_no_token() -> None:
    assert "security" not in operations()[LOGIN]


def test_every_other_api_operation_keeps_its_security_requirement() -> None:
    unprotected = {key for key, operation in operations().items() if not operation.get("security")}

    assert unprotected == {LOGIN}


def request_with(authorization: str | None) -> Request:
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Bearer abc.def", "bearer abc.def", "BEARER abc", "Bearer", "Basic abc", "abc"],
)
async def test_the_rate_limiter_reads_the_token_like_the_auth_scheme(
    authorization: str | None,
) -> None:
    request = request_with(authorization)

    assert bearer_token(request) == await oauth2_scheme(request)

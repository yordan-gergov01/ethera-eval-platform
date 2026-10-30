"""Authentication end to end: login, current user, every 401 case, logout and the API docs.

Role: pins the auth contract of /api/v1/auth (backend/api/v1/auth) and /api/v1/users/me with
  backend.core.tokens `JwtTokenService`: bearer login, problem-details 401s, logout revoking
  every session of the user, and the OpenAPI security scheme.
Used by: pytest (integration — needs the test database).
Depends on: `started_app`, `backend_settings`, `create_user`, `connect_as_app`, `login`,
  `token_for`, `bearer`, `ADMIN_PASSWORD` from tests/integration/conftest.py.
Key invariants: drives the real ASGI app and database, never mocks our own code; a wrong
  password, an unknown user and an inactive user get the identical 401; an expired token is
  minted with a past clock instead of waiting.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient, Response

from backend.core.settings import BackendSettings
from backend.core.tokens import JwtTokenService
from common_lib.permissions import Permission
from tests.integration.conftest import (
    ADMIN_PASSWORD,
    bearer,
    connect_as_app,
    create_user,
    login,
    token_for,
)

ME = "/api/v1/users/me"


def assert_unauthorized(response: Response, code: str) -> None:
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == code


# --- Login -----------------------------------------------------------------------------


async def test_login_returns_a_bearer_token(started_app: AsyncClient) -> None:
    response = await login(started_app, "admin", ADMIN_PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60
    assert body["access_token"]


async def test_username_is_case_insensitive_at_login(started_app: AsyncClient) -> None:
    assert (await login(started_app, "Admin", ADMIN_PASSWORD)).status_code == 200


async def test_wrong_password_unknown_user_and_inactive_user_look_the_same(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    await create_user(backend_settings, username="dora", password=ADMIN_PASSWORD, is_active=False)

    responses = [
        await login(started_app, "admin", "not-the-right-password"),
        await login(started_app, "nobody-like-this", ADMIN_PASSWORD),
        await login(started_app, "dora", ADMIN_PASSWORD),
    ]

    for response in responses:
        assert_unauthorized(response, "INVALID_CREDENTIALS")
    details = {r.json()["detail"] for r in responses}
    assert details == {"The username or password is incorrect."}


# --- Current user ----------------------------------------------------------------------


async def test_current_user_has_role_and_permissions(started_app: AsyncClient) -> None:
    token = await token_for(started_app, "admin", ADMIN_PASSWORD)

    response = await started_app.get(ME, headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["permissions"] == sorted(p.value for p in Permission)
    assert "password_hash" not in body


async def test_no_token_is_401(started_app: AsyncClient) -> None:
    assert_unauthorized(await started_app.get(ME), "AUTHENTICATION_FAILED")


async def test_invalid_token_is_401(started_app: AsyncClient) -> None:
    assert_unauthorized(await started_app.get(ME, headers=bearer("abc.def.ghi")), "INVALID_TOKEN")


async def test_expired_token_is_401(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    expired = JwtTokenService(
        secret=backend_settings.jwt_secret,
        issuer=backend_settings.jwt_issuer,
        audience=backend_settings.jwt_audience,
        lifetime=timedelta(minutes=30),
        leeway=timedelta(seconds=10),
        clock=lambda: long_ago,
    )
    connection = await connect_as_app(backend_settings)
    try:
        admin_id = await connection.fetchval("SELECT id FROM users WHERE username = 'admin'")
    finally:
        await connection.close()

    token = expired.issue(admin_id, token_version=0).token

    assert_unauthorized(await started_app.get(ME, headers=bearer(token)), "INVALID_TOKEN")


async def test_deactivated_user_with_a_still_valid_token_is_401(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    await create_user(backend_settings, username="erin", password=ADMIN_PASSWORD)
    token = await token_for(started_app, "erin", ADMIN_PASSWORD)
    assert (await started_app.get(ME, headers=bearer(token))).status_code == 200

    connection = await connect_as_app(backend_settings)
    try:
        await connection.execute("UPDATE users SET is_active = false WHERE username = 'erin'")
    finally:
        await connection.close()

    assert_unauthorized(await started_app.get(ME, headers=bearer(token)), "INVALID_TOKEN")


# --- Logout ----------------------------------------------------------------------------


async def test_logout_revokes_the_token(started_app: AsyncClient) -> None:
    token = await token_for(started_app, "admin", ADMIN_PASSWORD)

    response = await started_app.post("/api/v1/auth/logout", headers=bearer(token))

    assert response.status_code == 204
    assert_unauthorized(await started_app.get(ME, headers=bearer(token)), "INVALID_TOKEN")


async def test_logout_ends_every_session_of_the_user(started_app: AsyncClient) -> None:
    laptop = await token_for(started_app, "admin", ADMIN_PASSWORD)
    phone = await token_for(started_app, "admin", ADMIN_PASSWORD)

    await started_app.post("/api/v1/auth/logout", headers=bearer(laptop))

    assert_unauthorized(await started_app.get(ME, headers=bearer(phone)), "INVALID_TOKEN")
    assert (await login(started_app, "admin", ADMIN_PASSWORD)).status_code == 200


async def test_logout_needs_a_token(started_app: AsyncClient) -> None:
    assert_unauthorized(await started_app.post("/api/v1/auth/logout"), "AUTHENTICATION_FAILED")


# --- API documentation -----------------------------------------------------------------


async def test_docs_offer_the_password_flow_for_the_authorize_button(
    started_app: AsyncClient,
) -> None:
    schema = (await started_app.get("/openapi.json")).json()

    [scheme] = schema["components"]["securitySchemes"].values()
    assert scheme["type"] == "oauth2"
    assert scheme["flows"]["password"]["tokenUrl"] == "/api/v1/auth/login"
    assert schema["paths"][ME]["get"]["security"]


async def test_docs_describe_errors_as_problem_details(started_app: AsyncClient) -> None:
    schema = (await started_app.get("/openapi.json")).json()

    me_responses = schema["paths"][ME]["get"]["responses"]
    for status in ("401", "422", "500"):
        assert "application/problem+json" in me_responses[status]["content"], status
    assert "HTTPValidationError" not in schema["components"]["schemas"]

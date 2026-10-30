"""Mechanical guard: real flows never put personal data or secrets into the technical logs.

Role: enforces the Bible's never-log list (.claude/rules/observability.md, privacy.md) on the
  backend's actual handler output, not on a mocked logger.
Used by: pytest (integration; needs the test database and broker).
Depends on: `backend_settings` from tests/integration/conftest.py; the real app factory, whose
  `configure_logging` writes JSON lines to stdout, captured with `capsys`.
Key invariants: the app is created INSIDE each test, after `capsys` replaced stdout, so the
  handler writes into the capture; the capture is proven non-empty (anti-vacuity); every
  planted value — passwords, tokens, emails, full names, a query-string secret, the
  Authorization header — must be absent; the negative test proves a leak would be caught.
"""

from collections.abc import Iterable

import pytest
import structlog
from httpx import ASGITransport, AsyncClient

from backend.core.settings import BackendSettings
from backend.main import create_app

ADMIN_PASSWORD = "test-only-admin-password"
NEW_PASSWORD = "Never-Log-This-Passw0rd-71"
CHANGED_PASSWORD = "Second-Never-Logged-Passw0rd-72"
WRONG_PASSWORD = "Wrong-Password-Never-Logged-73"
EMAIL = "never.logged.person@example.org"
CHANGED_EMAIL = "still.never.logged@example.org"
FULL_NAME = "Neverlogged Personname"
QUERY_SECRET = "reset-token-never-logged-74"


def leaks(output: str, secrets: Iterable[str]) -> list[str]:
    """The planted values that appear anywhere in the captured output."""
    return sorted(secret for secret in secrets if secret in output)


async def _exercise_flows(client: AsyncClient) -> str:
    """Run the flows that handle personal data and secrets; return the admin token."""
    await client.post("/api/v1/auth/login", data={"username": "admin", "password": WRONG_PASSWORD})
    login = await client.post(
        "/api/v1/auth/login", data={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert login.status_code == 200
    token: str = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/users",
        headers=auth,
        json={
            "username": "neverlogged",
            "email": EMAIL,
            "full_name": FULL_NAME,
            "password": NEW_PASSWORD,
            "role": "user",
        },
    )
    assert created.status_code == 201
    await client.get(f"/api/v1/users/me?token={QUERY_SECRET}", headers=auth)
    await client.get("/api/v1/users/does-not-exist", headers=auth)

    user_login = await client.post(
        "/api/v1/auth/login", data={"username": "neverlogged", "password": NEW_PASSWORD}
    )
    user_auth = {"Authorization": f"Bearer {user_login.json()['access_token']}"}
    await client.patch("/api/v1/users/me", headers=user_auth, json={"email": CHANGED_EMAIL})
    await client.post(
        "/api/v1/users/me/password",
        headers=user_auth,
        json={"current_password": WRONG_PASSWORD, "new_password": CHANGED_PASSWORD},
    )
    await client.post(
        "/api/v1/users/me/password",
        headers=user_auth,
        json={"current_password": NEW_PASSWORD, "new_password": CHANGED_PASSWORD},
    )
    return token


async def test_real_flows_log_no_personal_data_or_secrets(
    backend_settings: BackendSettings, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(backend_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        token = await _exercise_flows(client)
    output = capsys.readouterr().out

    # Anti-vacuity: the flows did log, through the real handler.
    assert '"event": "user_created"' in output
    assert '"event": "password_changed"' in output
    secrets = [
        ADMIN_PASSWORD,
        NEW_PASSWORD,
        CHANGED_PASSWORD,
        WRONG_PASSWORD,
        EMAIL,
        CHANGED_EMAIL,
        FULL_NAME,
        QUERY_SECRET,
        token,
        backend_settings.jwt_secret.get_secret_value(),
    ]
    leaked_lines = [line for line in output.splitlines() if leaks(line, secrets)]
    assert leaks(output, secrets) == [], leaked_lines


async def test_the_guard_detects_a_planted_leak(
    backend_settings: BackendSettings, capsys: pytest.CaptureFixture[str]
) -> None:
    create_app(backend_settings)  # configures the real logging pipeline
    structlog.get_logger("leak").info("bad_line", note=f"contact {EMAIL}")
    output = capsys.readouterr().out
    assert leaks(output, [EMAIL, FULL_NAME]) == [EMAIL]

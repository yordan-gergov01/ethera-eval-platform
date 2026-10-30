"""Self-service end to end: a user changes their own profile and password.

Role: pins /api/v1/users/me and /api/v1/users/me/password (backend/api/v1/users,
  backend/services/users): profile updates with normalised name and email, 422 for forbidden or
  invalid fields, 409 for a taken email, a password change that revokes every token, and the
  password policy on the new password.
Used by: pytest (integration — needs the test database).
Depends on: `started_app`, `backend_settings`, `create_user`, `login`, `token_for`, `bearer`,
  `assert_problem`, `ADMIN_PASSWORD` from tests/integration/conftest.py; backend.dal.users
  `UserRepository` for the concurrency case.
Key invariants: drives the real ASGI app and database, never mocks our own code; a rejected
  change leaves the stored user untouched; a weak password is never echoed in the response; a
  concurrent email takeover is still 409 because the unique index decides.
"""

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient

from backend.core.settings import BackendSettings
from backend.dal.users import UserChanges, UserRepository
from common_lib.errors import ConflictError, ErrorCode
from tests.integration.conftest import (
    ADMIN_PASSWORD,
    assert_problem,
    bearer,
    create_user,
    login,
    token_for,
)

ME = "/api/v1/users/me"
PASSWORD = "/api/v1/users/me/password"
DORA_PASSWORD = "test-only-dora-password"
NEW_PASSWORD = "test-only-new-dora-password"


@pytest.fixture
async def dora(started_app: AsyncClient, backend_settings: BackendSettings) -> str:
    """A plain user's access token."""
    await create_user(backend_settings, username="dora", password=DORA_PASSWORD)
    return await token_for(started_app, "dora", DORA_PASSWORD)


# --- Profile ---------------------------------------------------------------------------


async def test_user_changes_own_name_and_email(started_app: AsyncClient, dora: str) -> None:
    response = await started_app.patch(
        ME,
        json={"full_name": "  Dora Explorer ", "email": "Dora.New@Example.COM"},
        headers=bearer(dora),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "Dora Explorer"
    assert body["email"] == "dora.new@example.com"
    assert body["role"] == "user"
    # Stored, not only echoed.
    assert (await started_app.get(ME, headers=bearer(dora))).json() == body


async def test_omitted_fields_stay_unchanged(started_app: AsyncClient, dora: str) -> None:
    response = await started_app.patch(ME, json={"full_name": "Dora"}, headers=bearer(dora))

    assert response.status_code == 200
    assert response.json()["email"] == "dora@example.com"


async def test_keeping_own_email_is_not_a_conflict(started_app: AsyncClient, dora: str) -> None:
    response = await started_app.patch(ME, json={"email": "dora@example.com"}, headers=bearer(dora))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"role": "admin"},
        {"is_active": False},
        {"full_name": "Dora", "role": "admin"},
        {"username": "someone-else"},
        {},
        {"email": None},
        {"full_name": "   "},
        {"email": "not-an-email"},
    ],
    ids=[
        "role",
        "is_active",
        "role with a valid field",
        "username",
        "empty",
        "null",
        "blank",
        "bad email",
    ],
)
async def test_invalid_profile_changes_are_422(
    started_app: AsyncClient, dora: str, body: dict[str, Any]
) -> None:
    response = await started_app.patch(ME, json=body, headers=bearer(dora))

    assert_problem(response, 422, "VALIDATION_FAILED")
    me = (await started_app.get(ME, headers=bearer(dora))).json()
    assert me["role"] == "user"
    assert me["full_name"] == "dora"


async def test_email_of_another_account_is_409(started_app: AsyncClient, dora: str) -> None:
    response = await started_app.patch(
        ME, json={"email": "ADMIN@example.com"}, headers=bearer(dora)
    )

    assert_problem(response, 409, "EMAIL_TAKEN")


async def test_concurrent_email_takeover_is_still_409(
    started_app: AsyncClient, backend_settings: BackendSettings, dora: str
) -> None:
    # Skips the service's check, as a concurrent request would: the unique index decides.
    me = (await started_app.get(ME, headers=bearer(dora))).json()

    with pytest.raises(ConflictError) as raised:
        await UserRepository().update_user(UUID(me["id"]), UserChanges(email="admin@example.com"))

    assert raised.value.code is ErrorCode.EMAIL_TAKEN


async def test_profile_changes_need_a_token(started_app: AsyncClient) -> None:
    response = await started_app.patch(ME, json={"full_name": "Nobody"})

    assert_problem(response, 401, "AUTHENTICATION_FAILED")


# --- Password --------------------------------------------------------------------------


async def test_password_change_revokes_every_token(started_app: AsyncClient, dora: str) -> None:
    second_session = await token_for(started_app, "dora", DORA_PASSWORD)

    response = await started_app.post(
        PASSWORD,
        json={"current_password": DORA_PASSWORD, "new_password": NEW_PASSWORD},
        headers=bearer(dora),
    )

    assert response.status_code == 204
    for token in (dora, second_session):
        assert_problem(await started_app.get(ME, headers=bearer(token)), 401, "INVALID_TOKEN")
    assert (await login(started_app, "dora", DORA_PASSWORD)).status_code == 401
    assert (await login(started_app, "dora", NEW_PASSWORD)).status_code == 200


async def test_wrong_current_password_is_422_and_keeps_the_session(
    started_app: AsyncClient, dora: str
) -> None:
    response = await started_app.post(
        PASSWORD,
        json={"current_password": "not-the-current-one", "new_password": NEW_PASSWORD},
        headers=bearer(dora),
    )

    assert_problem(response, 422, "INVALID_CURRENT_PASSWORD")
    assert (await started_app.get(ME, headers=bearer(dora))).status_code == 200
    assert (await login(started_app, "dora", DORA_PASSWORD)).status_code == 200


@pytest.mark.parametrize(
    ("new_password", "reason"),
    [
        ("too-short", "at least 12 characters"),
        ("x" * 129, "at most 128 characters"),
        ("password1234", "too common"),
        ("DORA@example.com", "same as the username or email"),
    ],
)
async def test_weak_new_password_is_422(
    started_app: AsyncClient, dora: str, new_password: str, reason: str
) -> None:
    response = await started_app.post(
        PASSWORD,
        json={"current_password": DORA_PASSWORD, "new_password": new_password},
        headers=bearer(dora),
    )

    body = assert_problem(response, 422, "WEAK_PASSWORD")
    assert reason in body["detail"]
    assert new_password not in response.text
    assert (await login(started_app, "dora", DORA_PASSWORD)).status_code == 200


async def test_password_change_rejects_unknown_fields(started_app: AsyncClient, dora: str) -> None:
    response = await started_app.post(
        PASSWORD,
        json={"current_password": DORA_PASSWORD, "new_password": NEW_PASSWORD, "username": "x"},
        headers=bearer(dora),
    )

    assert_problem(response, 422, "VALIDATION_FAILED")


async def test_password_change_needs_a_token(started_app: AsyncClient) -> None:
    response = await started_app.post(
        PASSWORD, json={"current_password": ADMIN_PASSWORD, "new_password": NEW_PASSWORD}
    )

    assert_problem(response, 401, "AUTHENTICATION_FAILED")

"""User administration end to end: permissions, account rules and last-admin protection.

Role: pins the admin side of /api/v1/users (backend/api/v1/users, backend/services/users,
  backend.dal.users `UserRepository`): 403 for plain users, 401 without a token, paging,
  create, update, conflicts, and the guard that always keeps one active administrator.
Used by: pytest (integration — needs the test database).
Depends on: `started_app`, `backend_settings`, `create_user`, `connect_as_app`, `login`,
  `token_for`, `bearer`, `assert_problem`, `ADMIN_PASSWORD` from tests/integration/conftest.py.
Key invariants: drives the real ASGI app and database, never mocks our own code; concurrency
  cases call the repository directly to skip the service check, so the unique index and the
  `ACCOUNT_GUARD_LOCK_ID` advisory lock are what decide; a concurrent demotion is held mid-way
  in a real open transaction.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from backend.core.settings import BackendSettings
from backend.dal.users import NewUser, UserChanges, UserRepository
from backend.dal.users.repository import ACCOUNT_GUARD_LOCK_ID
from common_lib.errors import ConflictError, ErrorCode
from tests.integration.conftest import (
    ADMIN_PASSWORD,
    assert_problem,
    bearer,
    connect_as_app,
    create_user,
    login,
    token_for,
)

USERS = "/api/v1/users"
ME = "/api/v1/users/me"
PASSWORD = "test-only-plain-user-password"
NEW_PASSWORD = "test-only-carol-password"


@pytest.fixture
async def admin(started_app: AsyncClient) -> str:
    return await token_for(started_app, "admin", ADMIN_PASSWORD)


@pytest.fixture
async def dora(started_app: AsyncClient, backend_settings: BackendSettings) -> str:
    """A plain user's access token."""
    await create_user(backend_settings, username="dora", password=PASSWORD)
    return await token_for(started_app, "dora", PASSWORD)


async def user_id(client: AsyncClient, token: str) -> str:
    me: dict[str, Any] = (await client.get(ME, headers=bearer(token))).json()
    return str(me["id"])


def carol(**overrides: Any) -> dict[str, Any]:
    return {
        "username": "carol",
        "email": "carol@example.com",
        "full_name": "Carol",
        "password": NEW_PASSWORD,
        "role": "user",
    } | overrides


# --- Permissions -----------------------------------------------------------------------


async def test_plain_user_gets_403_on_every_admin_endpoint(
    started_app: AsyncClient, admin: str, dora: str
) -> None:
    target = await user_id(started_app, admin)
    calls = [
        started_app.get(USERS, headers=bearer(dora)),
        started_app.get(f"{USERS}/{target}", headers=bearer(dora)),
        started_app.post(USERS, json=carol(), headers=bearer(dora)),
        started_app.patch(f"{USERS}/{target}", json={"is_active": False}, headers=bearer(dora)),
    ]

    for call in calls:
        assert_problem(await call, 403, "PERMISSION_DENIED")
    # Nothing changed on the way.
    assert (await login(started_app, "carol", NEW_PASSWORD)).status_code == 401
    assert (await started_app.get(ME, headers=bearer(admin))).status_code == 200


async def test_admin_endpoints_need_a_token(started_app: AsyncClient) -> None:
    target = uuid4()
    calls = [
        started_app.get(USERS),
        started_app.get(f"{USERS}/{target}"),
        started_app.post(USERS, json=carol()),
        started_app.patch(f"{USERS}/{target}", json={"is_active": False}),
    ]

    for call in calls:
        assert_problem(await call, 401, "AUTHENTICATION_FAILED")


# --- Reading ---------------------------------------------------------------------------


async def test_admin_lists_users_page_by_page(
    started_app: AsyncClient, backend_settings: BackendSettings, admin: str
) -> None:
    for name in ("erin", "frank", "grace"):
        await create_user(backend_settings, username=name, password=PASSWORD)

    response = await started_app.get(USERS, params={"limit": 2, "offset": 1}, headers=bearer(admin))

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (4, 2, 1)
    assert [user["username"] for user in body["items"]] == ["erin", "frank"]
    assert set(body["items"][0]) == {
        "id",
        "username",
        "email",
        "full_name",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    }


async def test_default_page_size_is_50(started_app: AsyncClient, admin: str) -> None:
    body = (await started_app.get(USERS, headers=bearer(admin))).json()

    assert (body["limit"], body["offset"], body["total"]) == (50, 0, 1)


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
async def test_page_bounds_are_enforced(
    started_app: AsyncClient, admin: str, params: dict[str, int]
) -> None:
    response = await started_app.get(USERS, params=params, headers=bearer(admin))

    assert_problem(response, 422, "VALIDATION_FAILED")


async def test_admin_reads_one_user(started_app: AsyncClient, admin: str, dora: str) -> None:
    target = await user_id(started_app, dora)

    response = await started_app.get(f"{USERS}/{target}", headers=bearer(admin))

    assert response.status_code == 200
    assert response.json()["username"] == "dora"
    assert "password_hash" not in response.text


async def test_unknown_user_is_404(started_app: AsyncClient, admin: str) -> None:
    response = await started_app.get(f"{USERS}/{uuid4()}", headers=bearer(admin))

    assert_problem(response, 404, "USER_NOT_FOUND")


# --- Creating --------------------------------------------------------------------------


async def test_admin_creates_a_user_who_can_log_in(started_app: AsyncClient, admin: str) -> None:
    response = await started_app.post(
        USERS, json=carol(username="Carol", email="Carol@Example.com"), headers=bearer(admin)
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert response.headers["location"] == f"{USERS}/{body['id']}"
    assert (body["username"], body["email"], body["role"]) == ("carol", "carol@example.com", "user")
    assert body["is_active"] is True
    assert NEW_PASSWORD not in response.text
    assert (
        await started_app.get(response.headers["location"], headers=bearer(admin))
    ).json() == body
    assert (await login(started_app, "carol", NEW_PASSWORD)).status_code == 200


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"username": "ADMIN"}, "USERNAME_TAKEN"),
        ({"email": "admin@EXAMPLE.com"}, "EMAIL_TAKEN"),
    ],
)
async def test_duplicate_username_or_email_is_409(
    started_app: AsyncClient, admin: str, overrides: dict[str, str], code: str
) -> None:
    response = await started_app.post(USERS, json=carol(**overrides), headers=bearer(admin))

    assert_problem(response, 409, code)


@pytest.mark.parametrize(
    "password", ["short-one", "password1234", "carol@example.com"], ids=["short", "common", "email"]
)
async def test_weak_password_is_rejected_on_create(
    started_app: AsyncClient, admin: str, password: str
) -> None:
    response = await started_app.post(USERS, json=carol(password=password), headers=bearer(admin))

    assert_problem(response, 422, "WEAK_PASSWORD")
    assert password not in response.text


@pytest.mark.parametrize(
    "overrides",
    [{"role": "superuser"}, {"is_active": False}, {"username": "-carol"}, {"full_name": ""}],
    ids=["unknown role", "extra field", "bad username", "blank name"],
)
async def test_invalid_new_user_is_422(
    started_app: AsyncClient, admin: str, overrides: dict[str, Any]
) -> None:
    response = await started_app.post(USERS, json=carol(**overrides), headers=bearer(admin))

    assert_problem(response, 422, "VALIDATION_FAILED")


async def test_concurrent_duplicate_create_is_still_409(started_app: AsyncClient) -> None:
    # Skips the service's check, as a concurrent request would: the unique index decides.
    duplicate = NewUser(
        username="admin",
        email="someone@example.com",
        full_name="Someone",
        password_hash="not-a-real-hash",
        role_name="user",
    )

    with pytest.raises(ConflictError) as raised:
        await UserRepository().create(duplicate)

    assert raised.value.code is ErrorCode.USERNAME_TAKEN


# --- Updating --------------------------------------------------------------------------


async def test_role_change_applies_on_the_next_request(
    started_app: AsyncClient, admin: str, dora: str
) -> None:
    target = await user_id(started_app, dora)

    response = await started_app.patch(
        f"{USERS}/{target}", json={"role": "admin", "full_name": "Dora D."}, headers=bearer(admin)
    )

    assert response.status_code == 200, response.text
    assert (response.json()["role"], response.json()["full_name"]) == ("admin", "Dora D.")
    # Same token, new permissions: they are loaded per request, not stored in the token.
    assert (await started_app.get(USERS, headers=bearer(dora))).status_code == 200


async def test_deactivated_user_is_locked_out_and_can_be_reactivated(
    started_app: AsyncClient, admin: str, dora: str
) -> None:
    target = f"{USERS}/{await user_id(started_app, dora)}"

    response = await started_app.patch(target, json={"is_active": False}, headers=bearer(admin))

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert_problem(await started_app.get(ME, headers=bearer(dora)), 401, "INVALID_TOKEN")
    assert_problem(await login(started_app, "dora", PASSWORD), 401, "INVALID_CREDENTIALS")

    await started_app.patch(target, json={"is_active": True}, headers=bearer(admin))
    assert (await login(started_app, "dora", PASSWORD)).status_code == 200


@pytest.mark.parametrize(
    "body",
    [{"role": "user"}, {"is_active": False}, {"full_name": "Me", "role": "user"}],
)
async def test_admin_cannot_change_own_role_or_status(
    started_app: AsyncClient, admin: str, body: dict[str, Any]
) -> None:
    own = f"{USERS}/{await user_id(started_app, admin)}"

    response = await started_app.patch(own, json=body, headers=bearer(admin))

    assert_problem(response, 403, "SELF_MODIFICATION_FORBIDDEN")
    me = (await started_app.get(ME, headers=bearer(admin))).json()
    assert (me["role"], me["full_name"]) == ("admin", "Administrator")


async def test_admin_may_edit_own_name_and_email_by_id(
    started_app: AsyncClient, admin: str
) -> None:
    own = f"{USERS}/{await user_id(started_app, admin)}"

    response = await started_app.patch(
        own, json={"full_name": "Ada Admin", "email": "ada@example.com"}, headers=bearer(admin)
    )

    assert response.status_code == 200, response.text
    assert (response.json()["full_name"], response.json()["email"]) == (
        "Ada Admin",
        "ada@example.com",
    )


async def test_taken_email_on_update_is_409(
    started_app: AsyncClient, admin: str, dora: str
) -> None:
    target = f"{USERS}/{await user_id(started_app, dora)}"

    response = await started_app.patch(
        target, json={"email": "admin@example.com"}, headers=bearer(admin)
    )

    assert_problem(response, 409, "EMAIL_TAKEN")


async def test_update_of_unknown_user_is_404(started_app: AsyncClient, admin: str) -> None:
    response = await started_app.patch(
        f"{USERS}/{uuid4()}", json={"full_name": "Nobody"}, headers=bearer(admin)
    )

    assert_problem(response, 404, "USER_NOT_FOUND")


@pytest.mark.parametrize(
    "body", [{}, {"role": None}, {"username": "renamed"}, {"password": "x" * 20}]
)
async def test_invalid_update_is_422(
    started_app: AsyncClient, admin: str, dora: str, body: dict[str, Any]
) -> None:
    target = f"{USERS}/{await user_id(started_app, dora)}"

    response = await started_app.patch(target, json=body, headers=bearer(admin))

    assert_problem(response, 422, "VALIDATION_FAILED")


# --- Last active administrator ---------------------------------------------------------


async def test_last_active_holder_cannot_be_deactivated_or_demoted(
    started_app: AsyncClient, admin: str
) -> None:
    # Over HTTP the self rule already protects a lone admin; the guard is the database
    # rule underneath, checked directly here.
    only_admin = UUID(await user_id(started_app, admin))
    repository = UserRepository()

    for changes in (UserChanges(is_active=False), UserChanges(role_name="user")):
        applied = await repository.update_user(
            only_admin, changes, keep_active_holder_of="users:update"
        )
        assert applied is False

    me = (await started_app.get(ME, headers=bearer(admin))).json()
    assert me["role"] == "admin"


async def test_two_admins_demoting_each_other_leave_one_admin(
    started_app: AsyncClient, backend_settings: BackendSettings, admin: str
) -> None:
    await create_user(backend_settings, username="bea", password=PASSWORD, role="admin")
    bea = await token_for(started_app, "bea", PASSWORD)
    admin_id, bea_id = [UUID(await user_id(started_app, token)) for token in (admin, bea)]

    # A concurrent guarded change, caught mid-way: it holds the guard lock and has
    # demoted the admin, but has not committed yet.
    other = await connect_as_app(backend_settings)
    try:
        transaction = other.transaction()
        await transaction.start()
        await other.execute("SELECT pg_advisory_xact_lock($1)", ACCOUNT_GUARD_LOCK_ID)
        await other.execute(
            "UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'user') WHERE id = $1",
            admin_id,
        )

        demote_bea = asyncio.create_task(
            UserRepository().update_user(
                bea_id, UserChanges(role_name="user"), keep_active_holder_of="users:update"
            )
        )
        await asyncio.sleep(0.5)
        # Without the lock it would count the admin as still active and demote bea too.
        assert not demote_bea.done()

        await transaction.commit()
        assert await demote_bea is False
        admins = await other.fetchval(
            "SELECT count(*) FROM users u JOIN roles r ON r.id = u.role_id "
            "WHERE r.name = 'admin' AND u.is_active"
        )
    finally:
        await other.close()
    assert admins == 1

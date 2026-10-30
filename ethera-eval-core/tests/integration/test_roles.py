"""Roles end to end: the role list for administrators and nobody else.

Role: pins GET /api/v1/roles (backend/api/v1/roles): administrators get every role with its
  permissions as in common_lib.permissions `DEFAULT_ROLE_GRANTS`; a plain user is 403, no
  token is 401.
Used by: pytest (integration — needs the test database).
Depends on: `started_app`, `backend_settings`, `create_user`, `token_for`, `bearer`,
  `assert_problem`, `ADMIN_PASSWORD` from tests/integration/conftest.py.
Key invariants: drives the real ASGI app and database, never mocks our own code; the expected
  list is derived from the code's grants, not hard-coded.
"""

from httpx import AsyncClient

from backend.core.settings import BackendSettings
from common_lib.permissions import DEFAULT_ROLE_GRANTS
from tests.integration.conftest import (
    ADMIN_PASSWORD,
    assert_problem,
    bearer,
    create_user,
    token_for,
)

ROLES = "/api/v1/roles"


async def test_admin_lists_roles_with_their_permissions(started_app: AsyncClient) -> None:
    admin = await token_for(started_app, "admin", ADMIN_PASSWORD)

    response = await started_app.get(ROLES, headers=bearer(admin))

    assert response.status_code == 200
    assert response.json() == [
        {"name": role.value, "permissions": sorted(DEFAULT_ROLE_GRANTS[role])}
        for role in sorted(DEFAULT_ROLE_GRANTS)
    ]


async def test_plain_user_cannot_list_roles(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    await create_user(backend_settings, username="dora", password="test-only-dora-password")
    dora = await token_for(started_app, "dora", "test-only-dora-password")

    assert_problem(await started_app.get(ROLES, headers=bearer(dora)), 403, "PERMISSION_DENIED")


async def test_listing_roles_needs_a_token(started_app: AsyncClient) -> None:
    assert_problem(await started_app.get(ROLES), 401, "AUTHENTICATION_FAILED")

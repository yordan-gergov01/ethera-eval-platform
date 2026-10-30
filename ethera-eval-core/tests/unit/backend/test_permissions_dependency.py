"""Permission checks: 401 before 403, every listed permission required, visible in OpenAPI.

Role: pins backend.api.dependencies.permissions `require_permissions`: every listed permission
  is required, a missing token is 401 before any 403, a denial is logged with the missing
  permissions, the requirement shows in OpenAPI, and at least one permission must be named.
Used by: pytest (unit; one test is also a source-scanning architecture check).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; callers
  built from common_lib.permissions `DEFAULT_ROLE_GRANTS` and injected by overriding
  `get_current_user`. No services.
Key invariants: the backend/api layer never checks role names (scanned in the source), so
  "admins only" is always expressed through grants.
"""

import json
import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.permissions import require_permissions
from backend.core.settings import BackendSettings
from backend.main import create_app
from backend.services.auth import CurrentUser
from common_lib.permissions import DEFAULT_ROLE_GRANTS, Permission, RoleName

BACKEND_API = Path(__file__).resolve().parents[3] / "backend" / "api"


def user_with(role: RoleName, *granted: Permission) -> CurrentUser:
    """A caller with the role's default grants plus `granted`."""
    return CurrentUser(
        id=uuid4(),
        username=role.value,
        email=f"{role.value}@example.com",
        full_name=role.value,
        role=role.value,
        permissions=DEFAULT_ROLE_GRANTS[role] | frozenset(granted),
    )


def build_app(caller: CurrentUser | None) -> FastAPI:
    app = create_app(BackendSettings())

    @app.get("/api/v1/users-only", dependencies=[require_permissions(Permission.USERS_READ)])
    async def users_only() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get(
        "/api/v1/two-permissions",
        dependencies=[require_permissions(Permission.USERS_READ, Permission.USERS_CREATE)],
    )
    async def two_permissions() -> dict[str, str]:
        return {"ok": "yes"}

    if caller is not None:
        app.dependency_overrides[get_current_user] = lambda: caller
    return app


async def get(app: FastAPI, path: str) -> tuple[int, dict[str, object]]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    return response.status_code, response.json()


async def test_admin_passes_every_check() -> None:
    app = build_app(user_with(RoleName.ADMIN))

    for path in ("/api/v1/users-only", "/api/v1/two-permissions"):
        assert (await get(app, path))[0] == 200, path


async def test_plain_user_is_forbidden_without_the_permission() -> None:
    status, body = await get(build_app(user_with(RoleName.USER)), "/api/v1/users-only")

    assert status == 403
    assert body["code"] == "PERMISSION_DENIED"


async def test_plain_user_passes_with_the_permission() -> None:
    caller = user_with(RoleName.USER, Permission.USERS_READ)

    assert (await get(build_app(caller), "/api/v1/users-only"))[0] == 200


async def test_every_listed_permission_is_required() -> None:
    caller = user_with(RoleName.USER, Permission.USERS_READ)

    assert (await get(build_app(caller), "/api/v1/two-permissions"))[0] == 403


async def test_missing_token_is_401_not_403() -> None:
    status, body = await get(build_app(caller=None), "/api/v1/users-only")

    assert status == 401
    assert body["code"] == "AUTHENTICATION_FAILED"


async def test_denial_is_logged_with_the_missing_permissions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = build_app(user_with(RoleName.USER))
    await get(app, "/api/v1/two-permissions")

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    [denied] = [line for line in lines if line["event"] == "permission_denied"]
    assert denied["missing"] == ["users:create", "users:read"]
    assert denied["level"] == "warning"


def test_required_permissions_appear_in_openapi() -> None:
    schema = build_app(user_with(RoleName.ADMIN)).openapi()

    [requirement] = schema["paths"]["/api/v1/two-permissions"]["get"]["security"]
    assert sorted(next(iter(requirement.values()))) == ["users:create", "users:read"]


def test_at_least_one_permission_must_be_named() -> None:
    with pytest.raises(ValueError, match="at least one permission"):
        require_permissions()


def test_the_api_layer_never_checks_role_names() -> None:
    # Endpoints check permissions only; "admins only" is expressed through grants.
    role_check = re.compile(r"\brole\s*(==|!=|in\b)|RoleName\.|[\"']admin[\"']")
    offenders = [
        f"{path.relative_to(BACKEND_API)}:{number}"
        for path in BACKEND_API.rglob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if role_check.search(line)
    ]

    assert offenders == []

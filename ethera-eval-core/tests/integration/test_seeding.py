"""Seeding against PostgreSQL: grants follow the code, the admin is created once.

Role: pins backend/services/seeding at startup: permissions and role grants match
  common_lib.permissions, permissions removed from the code are removed from the database, and
  the admin account is created once with a verifiable Argon2id hash.
Used by: pytest (integration — needs the test database).
Depends on: `started_app`, `backend_settings`, `connect_as_app`, `ADMIN_PASSWORD` from
  tests/integration/conftest.py.
Key invariants: a restart with a different admin password changes nothing; assertions read the
  stored rows directly as the app role.
"""

from httpx import AsyncClient
from pydantic import SecretStr

from backend.core.security import Argon2PasswordHasher
from backend.core.settings import BackendSettings
from backend.main import create_app
from common_lib.permissions import DEFAULT_ROLE_GRANTS, Permission
from tests.integration.conftest import ADMIN_PASSWORD, connect_as_app


async def _grants(settings: BackendSettings) -> dict[str, set[str]]:
    connection = await connect_as_app(settings)
    try:
        # Every role appears, including one that holds no permission.
        rows = await connection.fetch(
            "SELECT r.name AS role, p.code AS code FROM roles r "
            "LEFT JOIN role_permissions rp ON rp.role_id = r.id "
            "LEFT JOIN permissions p ON p.id = rp.permission_id"
        )
    finally:
        await connection.close()
    grants: dict[str, set[str]] = {}
    for row in rows:
        codes = grants.setdefault(row["role"], set())
        if row["code"] is not None:
            codes.add(row["code"])
    return grants


async def _admin(settings: BackendSettings) -> dict[str, object]:
    connection = await connect_as_app(settings)
    try:
        row = await connection.fetchrow(
            "SELECT u.username, u.email, u.password_hash, u.is_active, r.name AS role "
            "FROM users u JOIN roles r ON r.id = u.role_id WHERE u.username = 'admin'"
        )
    finally:
        await connection.close()
    assert row is not None
    return dict(row)


async def _restart(settings: BackendSettings) -> None:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        pass


async def test_permissions_and_grants_match_the_code(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    expected = {
        role.value: {p.value for p in permissions}
        for role, permissions in DEFAULT_ROLE_GRANTS.items()
    }

    assert await _grants(backend_settings) == expected


async def test_admin_account_is_created_with_a_verifiable_hash(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    admin = await _admin(backend_settings)

    assert admin["email"] == "admin@example.com"
    assert admin["role"] == "admin"
    assert admin["is_active"] is True
    password_hash = str(admin["password_hash"])
    assert password_hash.startswith("$argon2id$")
    assert (await Argon2PasswordHasher().verify(ADMIN_PASSWORD, password_hash)).valid


async def test_restart_with_a_new_admin_password_changes_nothing(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    before = await _admin(backend_settings)
    changed = backend_settings.model_copy(
        update={"admin_password": SecretStr("a-completely-different-password")}
    )

    await _restart(changed)

    assert await _admin(backend_settings) == before


async def test_permissions_removed_from_the_code_are_removed_from_the_database(
    started_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    connection = await connect_as_app(backend_settings)
    try:
        await connection.execute(
            "INSERT INTO permissions (id, code) VALUES (gen_random_uuid(), 'legacy:permission')"
        )
    finally:
        await connection.close()

    await _restart(backend_settings)

    stored = set().union(*(await _grants(backend_settings)).values())
    assert stored == {p.value for p in Permission}

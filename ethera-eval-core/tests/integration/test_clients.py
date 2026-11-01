"""Clients and Client Memberships against PostgreSQL: create-only, idempotent, per user.

Role: pins backend.services.clients `ensure_client`, `ensure_membership` and
  `list_member_client_ids` on the runtime pool: repeated and concurrent calls create one row and
  never touch it; an unknown user or Client is a NotFoundError; each user's member Client IDs are
  their own, sorted, and empty without memberships (tenant isolation of the read).
Used by: pytest (integration — needs the test database).
Depends on: `started_app`, `backend_settings`, `create_user`, `connect_as_app` from
  tests/integration/conftest.py.
Key invariants: assertions read the stored rows directly; `created_at` proves the existing row
  was not rewritten.
"""

import asyncio
from uuid import UUID, uuid4

import pytest

from backend.core.settings import BackendSettings
from backend.services.clients import ensure_client, ensure_membership, list_member_client_ids
from common_lib.errors import NotFoundError
from tests.integration.conftest import connect_as_app, create_user

pytestmark = pytest.mark.usefixtures("started_app")


async def _user(settings: BackendSettings, username: str) -> UUID:
    await create_user(settings, username=username, password="test-only-client-password")
    connection = await connect_as_app(settings)
    try:
        user_id: UUID = await connection.fetchval(
            "SELECT id FROM users WHERE username = $1", username
        )
        return user_id
    finally:
        await connection.close()


async def _fetch(settings: BackendSettings, query: str) -> list[tuple[object, ...]]:
    connection = await connect_as_app(settings)
    try:
        return [tuple(row) for row in await connection.fetch(query)]
    finally:
        await connection.close()


async def test_ensure_client_creates_once_and_never_touches_it(
    backend_settings: BackendSettings,
) -> None:
    await ensure_client("acme")
    before = await _fetch(backend_settings, "SELECT id, client_id, created_at FROM clients")

    await ensure_client("acme")
    await asyncio.gather(ensure_client("acme"), ensure_client("acme"))

    assert await _fetch(backend_settings, "SELECT id, client_id, created_at FROM clients") == before
    assert [row[1] for row in before] == ["acme"]


async def test_ensure_membership_creates_once(backend_settings: BackendSettings) -> None:
    user_id = await _user(backend_settings, "member")
    await ensure_client("acme")

    await ensure_membership(user_id, "acme")
    before = await _fetch(backend_settings, "SELECT id, created_at FROM client_memberships")
    await asyncio.gather(ensure_membership(user_id, "acme"), ensure_membership(user_id, "acme"))

    assert await _fetch(backend_settings, "SELECT id, created_at FROM client_memberships") == before
    assert len(before) == 1


async def test_ensure_membership_unknown_client_or_user_not_found(
    backend_settings: BackendSettings,
) -> None:
    user_id = await _user(backend_settings, "member")
    await ensure_client("acme")

    with pytest.raises(NotFoundError):
        await ensure_membership(user_id, "no-such-client")
    with pytest.raises(NotFoundError):
        await ensure_membership(uuid4(), "acme")

    assert await _fetch(backend_settings, "SELECT id FROM client_memberships") == []


async def test_list_member_client_ids_each_user_sees_only_their_own_sorted(
    backend_settings: BackendSettings,
) -> None:
    first = await _user(backend_settings, "one")
    second = await _user(backend_settings, "two")
    none = await _user(backend_settings, "none")
    for client_id in ("zeta", "acme", "beta"):
        await ensure_client(client_id)
    await ensure_membership(first, "zeta")
    await ensure_membership(first, "acme")
    await ensure_membership(second, "beta")

    assert await list_member_client_ids(first) == ("acme", "zeta")
    assert await list_member_client_ids(second) == ("beta",)
    assert await list_member_client_ids(none) == ()

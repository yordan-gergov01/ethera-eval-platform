"""The audit writer against PostgreSQL: one row, in the caller's transaction.

Role: pins backend.services.audit `write_audit_row` on the runtime pool: every field is stored
  as given (details as JSON, the client address canonical or null); the row commits and rolls
  back WITH the caller's transaction; a refused detail writes nothing.
Used by: pytest (integration — needs the test database).
Depends on: `started_app`, `backend_settings`, `connect_as_app` from
  tests/integration/conftest.py; backend.dal.tenancy `tenant_transaction` (the transaction a
  domain service passes in).
Key invariants: assertions read the stored rows directly as the runtime role (SELECT is
  granted); `ProbeAction` stands in for the registry's members, which arrive with their first
  writer.
"""

from enum import StrEnum
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from backend.core.settings import BackendSettings
from backend.dal.tenancy import tenant_transaction
from backend.services.audit import AuditDetailsError, AuditEntry, write_audit_row
from common_lib.audit import AuditAction
from tests.integration.conftest import connect_as_app

pytestmark = pytest.mark.usefixtures("started_app")


class ProbeAction(StrEnum):
    """Stands in for the registry's members; an enum with members cannot be subclassed."""

    PROBE = "probe"


# write_audit_row reads only `.value`; the registry's own members arrive with their writer.
PROBE_ACTION = cast(AuditAction, ProbeAction.PROBE)


async def _admin_id(settings: BackendSettings) -> UUID:
    connection = await connect_as_app(settings)
    try:
        admin_id: UUID = await connection.fetchval(
            "SELECT id FROM users WHERE username = $1", settings.admin_username
        )
        return admin_id
    finally:
        await connection.close()


async def _rows(settings: BackendSettings) -> list[dict[str, Any]]:  # Any: column values
    connection = await connect_as_app(settings)
    try:
        rows = await connection.fetch(
            "SELECT id, actor_id, action, entity_type, entity_id, details::text AS details, "
            "client_ip, created_at FROM audit_rows"
        )
        return [dict(row) for row in rows]
    finally:
        await connection.close()


async def test_write_audit_row_stores_every_field(backend_settings: BackendSettings) -> None:
    actor_id, entity_id = await _admin_id(backend_settings), uuid4()
    entry = AuditEntry(
        actor_id=actor_id,
        action=PROBE_ACTION,
        entity_type="product",
        entity_id=entity_id,
        details={"product_id": entity_id, "to_version": 1, "changed_sections": []},
        client_ip="::ffff:127.0.0.1",
    )

    async with tenant_transaction(["acme"]) as connection:
        row_id = await write_audit_row(connection, entry)

    [row] = await _rows(backend_settings)
    assert row["id"] == row_id
    assert row["actor_id"] == actor_id
    assert row["action"] == "probe"
    assert row["entity_type"] == "product"
    assert row["entity_id"] == entity_id
    assert row["details"] == (
        f'{{"product_id": "{entity_id}", "to_version": 1, "changed_sections": []}}'
    )
    assert row["client_ip"] == "::ffff:127.0.0.1"
    assert row["created_at"].tzinfo is not None


async def test_write_audit_row_unknown_address_and_seed_store_null(
    backend_settings: BackendSettings,
) -> None:
    actor_id = await _admin_id(backend_settings)
    async with tenant_transaction([]) as connection:
        await write_audit_row(
            connection,
            AuditEntry(actor_id, PROBE_ACTION, "product", uuid4(), client_ip="unknown"),
        )
        await write_audit_row(connection, AuditEntry(actor_id, PROBE_ACTION, "product", uuid4()))

    assert [row["client_ip"] for row in await _rows(backend_settings)] == [None, None]


async def test_write_audit_row_rolls_back_with_the_change(
    backend_settings: BackendSettings,
) -> None:
    class ChangeFailedError(Exception):
        pass

    actor_id = await _admin_id(backend_settings)

    async def audited_change_that_fails() -> None:
        async with tenant_transaction(["acme"]) as connection:
            await write_audit_row(
                connection, AuditEntry(actor_id, PROBE_ACTION, "product", uuid4())
            )
            raise ChangeFailedError

    with pytest.raises(ChangeFailedError):
        await audited_change_that_fails()

    assert await _rows(backend_settings) == []


async def test_write_audit_row_refused_details_write_nothing(
    backend_settings: BackendSettings,
) -> None:
    actor_id = await _admin_id(backend_settings)
    entry = AuditEntry(
        actor_id, PROBE_ACTION, "product", uuid4(), details={"document": "a: b\nc: d"}
    )

    with pytest.raises(AuditDetailsError):
        async with tenant_transaction(["acme"]) as connection:
            await write_audit_row(connection, entry)

    assert await _rows(backend_settings) == []

"""Manifest changes as stored: one transaction per version, earlier versions never touched.

Role: pins evals.registry.services.manifests `replace_manifest` beyond the HTTP oracle — the
  version and its audit row commit together or not at all (INV-REG-03: a failure injected
  after the audit write leaves neither), and every earlier version is byte-for-byte unchanged
  after a replacement (INV-REG-07), read from the database directly.
Used by: pytest (integration; needs the test database and broker).
Depends on: `started_platform_app` from tests/integration/registry_fixtures.py;
  `backend_settings`, `connect_as_owner`, `token_for`, `bearer`, `ADMIN_PASSWORD` from
  tests/integration/conftest.py; pytest's `monkeypatch` (the injected failure).
Key invariants: the injected failure wraps the REAL audit writer (it writes, then raises), so
  the rollback is proven against a row that really was inserted.
"""

from typing import Any

import asyncpg
import pytest
from httpx import AsyncClient

from backend import AuditEntry, BackendSettings, TransactionConnection, write_audit_row
from evals.registry.services import manifests
from tests.integration.conftest import ADMIN_PASSWORD, bearer, connect_as_owner, token_for
from tests.integration.registry_fixtures import demo_document

PATH = "/api/v1/products/acme/support-bot/manifest"


class InjectedFailureError(Exception):
    pass


async def _stored(settings: BackendSettings) -> tuple[list[asyncpg.Record], int]:
    connection = await connect_as_owner(settings)
    try:
        versions = await connection.fetch(
            "SELECT id, version, document, bindings::text, allowed_providers::text, "
            "created_by_id, created_at FROM reg_manifests ORDER BY version"
        )
        audit_rows = await connection.fetchval("SELECT count(*) FROM audit_rows")
    finally:
        await connection.close()
    return list(versions), audit_rows


async def _put(api: AsyncClient, token: str, base: int, model: str) -> int:
    document = demo_document(model=model)
    response = await api.put(
        PATH, json={"base_version": base, "document": document}, headers=bearer(token)
    )
    return response.status_code


async def test_failure_after_the_audit_write_leaves_neither_version_nor_audit_row(
    started_platform_app: AsyncClient,
    backend_settings: BackendSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await token_for(started_platform_app, "admin", ADMIN_PASSWORD)
    before = await _stored(backend_settings)
    written: list[Any] = []

    async def write_then_fail(connection: TransactionConnection, entry: AuditEntry) -> None:
        written.append(await write_audit_row(connection, entry))
        raise InjectedFailureError

    monkeypatch.setattr(manifests, "write_audit_row", write_then_fail)
    # The platform answers an unexpected exception with a generic 500.
    assert await _put(started_platform_app, token, 1, "mock-gen-large-v2") == 500

    assert len(written) == 1
    assert await _stored(backend_settings) == before
    monkeypatch.undo()
    assert await _put(started_platform_app, token, 1, "mock-gen-large-v2") == 201


async def test_earlier_versions_are_unchanged_after_replacements(
    started_platform_app: AsyncClient, backend_settings: BackendSettings
) -> None:
    token = await token_for(started_platform_app, "admin", ADMIN_PASSWORD)
    [first], _ = await _stored(backend_settings)

    assert await _put(started_platform_app, token, 1, "mock-gen-large-v2") == 201
    after_one, _ = await _stored(backend_settings)
    assert await _put(started_platform_app, token, 2, "mock-gen-large-v3") == 201
    after_two, audit_rows = await _stored(backend_settings)

    assert [row["version"] for row in after_two] == [1, 2, 3]
    assert after_two[0] == first
    assert after_two[:2] == after_one
    assert audit_rows == 3

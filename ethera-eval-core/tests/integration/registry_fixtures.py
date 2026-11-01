"""The registry's test helpers, with exactly the signatures of contract §6 (slice 001).

Role: `started_platform_app` and `platform_app(settings)` (the full platform app — core plus
  every mounted module, `evals.app.create_app` — started and seeded on the test's database),
  `arrange_client`, `arrange_membership`, `arrange_product` (the seed's own path,
  `evals.registry.create_product`, with its `manifest_created` audit row), `product_entity_id`,
  `read_audit_rows` (as `AuditRowView` records) and `demo_document`.
Used by: the sealed oracle in tests/integration/registry/ (through its `_contract_fixtures.py`
  door) and the registry's own tests in tests/integration/evals/registry/.
Depends on: `backend_settings`, `connect_as_owner` from tests/integration/conftest.py;
  `evals.app.create_app`; the `backend` barrel (`ensure_client`, `ensure_membership`) and the
  `evals.registry` barrel; Tortoise (resolving usernames, and an ORM context when no app is live).
Key invariants: at most one app instance is live in the process (the ORM state is
  process-global): the `arrange_*` helpers use the live app's ORM, or open a short-lived one of
  their own only when none is live. Writes to client-owned tables go through
  `tenant_transaction([client_id])` inside the services, as the runtime role, so row security
  applies to fixtures too. Reads of audit rows and entity IDs use a direct owner connection
  (BYPASSRLS), never the app's pool.
"""

import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from backend import BackendSettings, ensure_client, ensure_membership, tortoise_config
from common_lib.models import User
from evals.app import create_app
from evals.MODULES import MODULES
from evals.registry import create_product
from evals.registry import demo_document as registry_demo_document
from tests.integration.conftest import connect_as_owner


@dataclass(frozen=True, slots=True)
class AuditRowView:
    """One audit row with exactly the fields of contract §5; `details` as a dict."""

    action: str
    actor_id: UUID
    entity_type: str
    entity_id: UUID
    details: dict[str, Any]  # Any: JSON values
    client_ip: str | None
    created_at: datetime


@asynccontextmanager
async def platform_app(settings: BackendSettings) -> AsyncIterator[AsyncClient]:
    """The full platform app on `settings`' database: started and seeded, shut down on exit."""
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


@pytest.fixture
async def started_platform_app(backend_settings: BackendSettings) -> AsyncIterator[AsyncClient]:
    """The full platform app, started and seeded as in contract §3.1; shut down at teardown."""
    async with platform_app(backend_settings) as client:
        yield client


def _orm(settings: BackendSettings) -> AbstractAsyncContextManager[None]:
    """The live app's ORM, or a short-lived one of the runtime role when no app is live."""
    if Tortoise.is_inited():
        return nullcontext()
    return _short_lived_orm(settings)


@asynccontextmanager
async def _short_lived_orm(settings: BackendSettings) -> AsyncIterator[None]:
    await Tortoise.init(config=tortoise_config(settings, MODULES))
    try:
        yield
    finally:
        await Tortoise.close_connections()


async def _user_id(username: str) -> UUID:
    user = await User.get(username=username)
    return user.id


async def arrange_client(settings: BackendSettings, client_id: str) -> None:
    """Create a Client."""
    async with _orm(settings):
        await ensure_client(client_id)


async def arrange_membership(settings: BackendSettings, username: str, client_id: str) -> None:
    """Make an existing user a member of an existing Client."""
    async with _orm(settings):
        await ensure_membership(await _user_id(username), client_id)


async def arrange_product(
    settings: BackendSettings,
    client_id: str,
    project_id: str,
    document: str,
    actor_username: str,
) -> None:
    """Create a Product with Manifest version 1 from `document`, the way the seed does."""
    async with _orm(settings):
        actor_id = await _user_id(actor_username)
        await create_product(client_id, project_id, document, actor_id, actor_username)


async def product_entity_id(settings: BackendSettings, client_id: str, project_id: str) -> str:
    """The `entity_id` the Product's audit rows carry."""
    connection = await connect_as_owner(settings)
    try:
        entity_id = await connection.fetchval(
            "SELECT id FROM reg_products WHERE client_id = $1 AND project_id = $2",
            client_id,
            project_id,
        )
    finally:
        await connection.close()
    assert entity_id is not None, (client_id, project_id)
    return str(entity_id)


async def read_audit_rows(settings: BackendSettings) -> list[AuditRowView]:
    """Every audit row, in unspecified order."""
    connection = await connect_as_owner(settings)
    try:
        rows = await connection.fetch(
            "SELECT action, actor_id, entity_type, entity_id, details, client_ip, created_at "
            "FROM audit_rows"
        )
    finally:
        await connection.close()
    return [
        AuditRowView(
            action=row["action"],
            actor_id=row["actor_id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            details=json.loads(row["details"]),
            client_ip=row["client_ip"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def demo_document(
    client_id: str = "acme", project_id: str = "support-bot", model: str = "mock-gen-small-v1"
) -> str:
    """The contract §3.1 demo document, re-targeted."""
    return registry_demo_document(client_id, project_id, model)

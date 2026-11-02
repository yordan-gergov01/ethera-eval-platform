"""The registry's connection-taking Product lookup is tenant-isolated (R-201).

Role: pins evals.registry.services.lookup `get_visible_product` against the real PostgreSQL, as
  the runtime role: it answers the Product only when the caller's tenant transaction admits its
  Client, and the registry's one PRODUCT_NOT_FOUND otherwise (INV-REG-10, D-014).
Used by: pytest (integration; needs the test database and broker).
Depends on: `started_platform_app` (this folder's conftest.py), `arrange_*` from
  tests/integration/registry_fixtures.py; the `evals.registry` barrel; the `backend` barrel.
Key invariants: `acme` (seeded) and `globex` each hold a Product `support-bot`; the "row security
  alone" case names globex with only acme in the tenant set; the "filter alone" case admits both
  Clients and asks acme for a Product only globex has.
"""

import pytest
from httpx import AsyncClient

from backend import BackendSettings, tenant_transaction
from common_lib.errors import ErrorCode, NotFoundError
from evals.registry import get_visible_product
from tests.integration.registry_fixtures import arrange_client, arrange_product, demo_document


@pytest.fixture
async def two_clients(
    started_platform_app: AsyncClient, backend_settings: BackendSettings
) -> BackendSettings:
    await arrange_client(backend_settings, "globex")
    for project_id in ("support-bot", "globex-only"):
        document = demo_document("globex", project_id)
        await arrange_product(backend_settings, "globex", project_id, document, "admin")
    return backend_settings


async def _not_found(client_ids: list[str], client_id: str, project_id: str) -> ErrorCode:
    with pytest.raises(NotFoundError) as raised:
        async with tenant_transaction(client_ids) as connection:
            await get_visible_product(connection, client_id, project_id)
    return raised.value.code


@pytest.mark.usefixtures("two_clients")
async def test_get_visible_product_only_within_the_tenant_set() -> None:
    async with tenant_transaction(["acme"]) as connection:
        acme = await get_visible_product(connection, "acme", "support-bot")

    assert (acme.client_id, acme.project_id) == ("acme", "support-bot")
    assert await _not_found(["acme"], "globex", "support-bot") == ErrorCode.PRODUCT_NOT_FOUND
    assert await _not_found(["acme", "globex"], "acme", "globex-only") == (
        ErrorCode.PRODUCT_NOT_FOUND
    )
    assert await _not_found([], "acme", "support-bot") == ErrorCode.PRODUCT_NOT_FOUND

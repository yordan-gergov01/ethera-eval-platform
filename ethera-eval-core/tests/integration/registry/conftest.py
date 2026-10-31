"""Registry oracle fixtures: the started platform app, bridged so its absence fails the test.

Role: exposes `api`, the client of the full platform app started and seeded as in
  specs/001-product-registry/contract.md §3.1, by requesting the implementer's
  `started_platform_app` fixture (contract §6) lazily.
Used by: every test module in tests/integration/registry/ that takes `api`.
Depends on: `tests.integration.registry_fixtures` (unsealed, imported by name when present);
  `backend_settings` from tests/integration/conftest.py (pulled in by `started_platform_app`);
  _contract_fixtures.py for the stand-in client.
Key invariants: while `started_platform_app` is absent, `api` is a stand-in whose first use fails
  the test body with "contract §6 fixture not yet provided" (a FAILED test, never a collection
  or setup error); at most one live app per test, because tests taking `api` never enter
  `platform_app` too.
"""

from typing import cast

import pytest
from httpx import AsyncClient

from tests.integration.registry._contract_fixtures import MissingPlatformClient, load_provider

_PROVIDER, _PROVIDER_ERROR = load_provider()
if _PROVIDER is not None and hasattr(_PROVIDER, "started_platform_app"):
    # Re-exported under its own name so pytest registers the implementer's fixture here.
    globals()["started_platform_app"] = _PROVIDER.started_platform_app


@pytest.fixture
def api(request: pytest.FixtureRequest) -> AsyncClient:
    """The started platform app's client, or a stand-in that fails the test on first use."""
    try:
        client: AsyncClient = request.getfixturevalue("started_platform_app")
    except pytest.FixtureLookupError:
        reason = _PROVIDER_ERROR or "fixture 'started_platform_app' is not defined"
        return cast(AsyncClient, MissingPlatformClient(reason))
    return client

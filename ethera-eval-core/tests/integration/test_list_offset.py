"""Paged lists answer any offset ≥ 0, however large, with an empty page instead of a 500.

Role: seals FIX-004 (and the registry twin, uncommitted) on the two paged lists,
  `GET /api/v1/users` and `GET /api/v1/products`: an offset beyond PostgreSQL's int8 range is
  capped at the SQL boundary, so the answer is 200 with no items, the real total and the
  caller's own offset echoed (contract §2.1: any integer ≥ 0, no 422 for it).
Used by: pytest (integration; needs the test database and broker).
Depends on: `started_platform_app` from tests/integration/registry_fixtures.py (the full app,
  core plus registry, seeded); `token_for`, `bearer`, `ADMIN_PASSWORD` from
  tests/integration/conftest.py.
Key invariants: the total is compared with an `offset=0` answer, never a hard-coded number; the
  seeded admin sees at least one item at offset 0 (anti-vacuity).
"""

import pytest
from httpx import AsyncClient

from tests.integration.conftest import ADMIN_PASSWORD, bearer, token_for
from tests.integration.registry_fixtures import started_platform_app

__all__ = ["started_platform_app"]

BEYOND_INT64 = 100_000_000_000_000_000_000


@pytest.mark.parametrize("route", ["/api/v1/users", "/api/v1/products"])
async def test_list_offset_beyond_int64_answers_empty_page_not_500(
    started_platform_app: AsyncClient, route: str
) -> None:
    client = started_platform_app
    auth = bearer(await token_for(client, "admin", ADMIN_PASSWORD))
    first = await client.get(route, headers=auth)
    assert first.status_code == 200, first.text
    assert first.json()["items"] != []

    response = await client.get(route, params={"offset": str(BEYOND_INT64)}, headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert body["total"] == first.json()["total"]
    assert body["offset"] == BEYOND_INT64

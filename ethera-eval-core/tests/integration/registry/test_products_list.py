"""Sealed oracle: GET /api/v1/products lists the caller's Products, paged and byte-ordered.

Role: pins contract §2.1 of specs/001-product-registry/contract.md — the summary shape, the
  current-version fields, membership scoping, code-point ordering by (client_id, project_id),
  paging with its boundaries (C-2), and the common 401 answers.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers through
  _contract_fixtures.py.
Key invariants: every refusal test first proves a 200 on the same route
  (test_list_requires_a_token, test_list_rejects_out_of_range_paging), so a missing route can
  never pass; ordering uses identifiers whose byte order differs from a locale collation
  (`a-c` before `ab`, `a-b` before `a0`).
"""

from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.conftest import assert_problem, bearer
from tests.integration.registry._contract_fixtures import (
    arrange_client,
    arrange_membership,
    arrange_product,
    demo_document,
)
from tests.integration.registry._registry_oracle import (
    ACME,
    PRODUCTS,
    SUPPORT_BOT,
    admin_token,
    arrange_member_product,
    assert_offset_timestamp,
    list_products,
    listed_ids,
    new_user,
    put_manifest,
    with_model,
)

ORDERED = [("a-c", "a-b"), ("a-c", "a0"), ("a-c", "ab"), ("a-c", "zz"), ("ab", "x")]


async def _arrange_ordering_set(api: AsyncClient, settings: Any) -> str:  # Any: opaque settings
    """Five Products in two Clients, created out of order; returns a member's token."""
    token = await new_user(api, settings, "lena", "user")
    await arrange_client(settings, "ab")
    await arrange_client(settings, "a-c")
    for client_id, project_id in reversed(ORDERED):
        await arrange_product(
            settings, client_id, project_id, demo_document(client_id, project_id), "admin"
        )
    await arrange_membership(settings, "lena", "ab")
    await arrange_membership(settings, "lena", "a-c")
    return token


async def test_list_requires_a_token(api: AsyncClient) -> None:
    admin = await admin_token(api)
    assert (await api.get(PRODUCTS, headers=bearer(admin))).status_code == 200
    assert_problem(await api.get(PRODUCTS), 401, "AUTHENTICATION_FAILED")
    assert_problem(await api.get(PRODUCTS, headers=bearer("not-a-token")), 401, "INVALID_TOKEN")


async def test_list_shows_the_seeded_product_summary_to_its_member(api: AsyncClient) -> None:
    listing = await list_products(api, await admin_token(api))
    assert (listing["total"], listing["limit"], listing["offset"]) == (1, 50, 0)
    [item] = listing["items"]
    assert_offset_timestamp(item.pop("changed_at"))
    assert item == {
        "client_id": ACME,
        "project_id": SUPPORT_BOT,
        "manifest_version": 1,
        "generation_binding": {
            "role": "generation",
            "provider": "mock",
            "model": "mock-gen-small-v1",
        },
        "changed_by": "admin",
    }


async def test_list_is_empty_for_a_user_without_memberships(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    assert (await list_products(api, await admin_token(api)))["total"] == 1
    for username, role in (("nora", "user"), ("ivan", "admin")):
        token = await new_user(api, backend_settings, username, role)
        listing = await list_products(api, token)
        assert (listing["items"], listing["total"]) == ([], 0), username


async def test_list_summary_follows_the_current_version(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    before = (await list_products(api, admin))["items"][0]
    erin = await new_user(api, backend_settings, "erin", "admin")
    await arrange_membership(backend_settings, "erin", ACME)
    response = await put_manifest(api, erin, 1, with_model("mock-gen-large-v2"))
    assert response.status_code == 201, response.text

    for token in (admin, erin):
        [item] = (await list_products(api, token))["items"]
        assert item["manifest_version"] == 2
        assert item["generation_binding"] == {
            "role": "generation",
            "provider": "mock",
            "model": "mock-gen-large-v2",
        }
        assert item["changed_by"] == "erin"
        assert_offset_timestamp(item["changed_at"])
        assert _instant(item["changed_at"]) >= _instant(before["changed_at"])


def _instant(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


async def test_list_holds_only_member_clients_in_code_point_order(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    lena = await _arrange_ordering_set(api, backend_settings)
    listing = await list_products(api, lena)
    assert listed_ids(listing) == ORDERED
    assert listing["total"] == len(ORDERED)
    # The seeded administrator is not a member of the new Clients.
    assert listed_ids(await list_products(api, await admin_token(api))) == [(ACME, SUPPORT_BOT)]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        pytest.param("?limit=2&offset=1", ORDERED[1:3], id="middle-page"),
        pytest.param("?limit=1", ORDERED[:1], id="limit-1"),
        pytest.param("?limit=100", ORDERED, id="limit-100"),
        pytest.param("?offset=0", ORDERED, id="offset-0"),
        pytest.param("?offset=4", ORDERED[4:], id="last-item"),
        pytest.param("?offset=5", [], id="offset-at-total"),
    ],
)
async def test_list_pages_with_limit_and_offset(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
    query: str,
    expected: list[tuple[str, str]],
) -> None:
    await admin_token(api)
    lena = await _arrange_ordering_set(api, backend_settings)
    listing = await list_products(api, lena, query)
    assert listed_ids(listing) == expected
    assert listing["total"] == len(ORDERED)
    params = dict(part.split("=") for part in query.lstrip("?").split("&"))
    assert listing["limit"] == int(params.get("limit", 50))
    assert listing["offset"] == int(params.get("offset", 0))


@pytest.mark.parametrize(
    "query",
    ["?limit=0", "?limit=101", "?offset=-1", "?limit=-1"],
)
async def test_list_rejects_out_of_range_paging(api: AsyncClient, query: str) -> None:
    admin = await admin_token(api)
    assert (await api.get(f"{PRODUCTS}?limit=1&offset=0", headers=bearer(admin))).status_code == 200
    response = await api.get(f"{PRODUCTS}{query}", headers=bearer(admin))
    assert_problem(response, 422, "VALIDATION_FAILED")


async def test_list_default_page_holds_fifty_of_fifty_one(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    bulk = await new_user(api, backend_settings, "bulk-reader", "user")
    await arrange_member_product(
        api, backend_settings, "bulk", "p00", member="bulk-reader", member_token=bulk
    )
    for index in range(1, 51):
        project_id = f"p{index:02d}"
        await arrange_product(
            backend_settings, "bulk", project_id, demo_document("bulk", project_id), "admin"
        )
    first = await list_products(api, bulk)
    assert (len(first["items"]), first["total"], first["limit"]) == (50, 51, 50)
    assert listed_ids(first) == [("bulk", f"p{i:02d}") for i in range(50)]
    rest = await list_products(api, bulk, "?offset=50")
    assert listed_ids(rest) == [("bulk", "p50")]

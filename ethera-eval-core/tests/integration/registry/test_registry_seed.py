"""Sealed oracle: the startup seed creates the demo Product once and never touches it again.

Role: pins contract §3.1 "The seed" of specs/001-product-registry/contract.md (spec FR-002,
  PP-010, INV-REG-14): Client `acme`, the seeded administrator's membership, Product
  `acme / support-bot` at version 1 with the demo document and its `manifest_created` row; a
  second start keeps a replaced version 2 and writes no second seed row.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers `platform_app`,
  `demo_document`, `read_audit_rows` and `product_entity_id` through _contract_fixtures.py.
Key invariants: restart tests never take `api` — they enter `platform_app` twice in sequence, so
  at most one app instance is live at a time, and read only through the live instance's client;
  the membership is the seeded administrator's alone: another admin does not see the Product.
"""

from typing import Any

from httpx import AsyncClient

from tests.integration.conftest import bearer
from tests.integration.registry._contract_fixtures import (
    demo_document,
    platform_app,
    product_entity_id,
    read_audit_rows,
)
from tests.integration.registry._registry_oracle import (
    ACME,
    DEMO_DOCUMENT,
    SUPPORT_BOT,
    admin_token,
    audit_rows_for,
    list_products,
    listed_ids,
    new_user,
    not_found_body,
    product_path,
    put_manifest,
    read_manifest,
    user_id,
    with_model,
)

V2_DOCUMENT = with_model("mock-gen-large-v2")


async def test_seed_creates_the_demo_product_at_version_one(api: AsyncClient) -> None:
    admin = await admin_token(api)
    manifest = await read_manifest(api, admin)
    assert manifest["version"] == 1
    assert manifest["created_by"] == "admin"
    assert manifest["document"] == demo_document()
    assert demo_document().rstrip("\n") == DEMO_DOCUMENT.rstrip("\n")
    assert listed_ids(await list_products(api, admin)) == [(ACME, SUPPORT_BOT)]


async def test_seed_writes_one_manifest_created_row_by_the_seeded_admin(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    entity_id = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    [row] = await audit_rows_for(backend_settings, entity_id)
    assert row.action == "manifest_created"
    assert str(row.actor_id) == await user_id(api, admin)
    assert row.entity_type == "product"
    assert row.client_ip is None
    assert row.details == {
        "product_id": entity_id,
        "client_id": ACME,
        "from_version": None,
        "to_version": 1,
        "changed_sections": [],
    }


async def test_seed_membership_belongs_to_the_seeded_admin_only(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    await read_manifest(api, admin)
    other = await new_user(api, backend_settings, "ivan", "admin")
    not_found_body(await api.get(product_path(), headers=bearer(other)))
    assert (await list_products(api, other))["items"] == []


async def test_restart_keeps_a_replaced_version_and_seeds_nothing_again(
    backend_settings: Any,  # Any: opaque settings
) -> None:
    async with platform_app(backend_settings) as first:
        admin = await admin_token(first)
        response = await put_manifest(first, admin, 1, V2_DOCUMENT)
        assert response.status_code == 201, response.text

    async with platform_app(backend_settings) as second:
        admin = await admin_token(second)
        manifest = await read_manifest(second, admin)
        assert (manifest["version"], manifest["document"]) == (2, V2_DOCUMENT)
        listing = await list_products(second, admin)
        assert listed_ids(listing) == [(ACME, SUPPORT_BOT)]
        assert listing["items"][0]["manifest_version"] == 2
        entity_id = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
        rows = await audit_rows_for(backend_settings, entity_id)
        assert sorted(row.action for row in rows) == ["manifest_created", "manifest_replaced"]
        assert (
            len([r for r in await read_audit_rows(backend_settings) if r.entity_type == "product"])
            == 2
        )


async def test_restart_without_changes_creates_nothing_new(
    backend_settings: Any,  # Any: opaque settings
) -> None:
    async with platform_app(backend_settings) as first:
        admin = await admin_token(first)
        before = await read_manifest(first, admin)
        assert before["version"] == 1

    async with platform_app(backend_settings) as second:
        admin = await admin_token(second)
        assert await read_manifest(second, admin) == before
        listing = await list_products(second, admin)
        assert (listed_ids(listing), listing["total"]) == ([(ACME, SUPPORT_BOT)], 1)
        rows = [r for r in await read_audit_rows(backend_settings) if r.entity_type == "product"]
        assert [row.action for row in rows] == ["manifest_created"]

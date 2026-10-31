"""Sealed oracle: one audit row per accepted Manifest version, exact and free of personal data.

Role: pins contract §5 "Audit rows" of specs/001-product-registry/contract.md (INV-REG-11,
  PP-010, C-12): `manifest_created` / `manifest_replaced` rows with the caller as actor, a
  stable UUID-shaped `entity_id` per Product, exact `details`, the caller's address, and nothing
  submitted (no document, model ID, username or email) inside `details`.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers `read_audit_rows` and
  `product_entity_id` through _contract_fixtures.py.
Key invariants: the actor is compared with the `id` of GET /api/v1/users/me, never with a value
  read from the database; rows are matched by `details.to_version`, never by position; in slice
  001 only `bindings` can change (product is fixed, `mock` is the only provider), so
  `changed_sections` is `["bindings"]` on every replacement.
"""

import ipaddress
import json
from typing import Any
from uuid import UUID

from httpx import AsyncClient

from tests.integration.registry._contract_fixtures import (
    arrange_membership,
    product_entity_id,
    read_audit_rows,
)
from tests.integration.registry._registry_oracle import (
    ACME,
    SUPPORT_BOT,
    admin_token,
    arrange_member_product,
    audit_rows_for,
    new_user,
    put_manifest,
    user_id,
    with_model,
)

DETAIL_KEYS = {"product_id", "client_id", "from_version", "to_version", "changed_sections"}


def by_version(rows: list[Any]) -> dict[int, Any]:  # Any: AuditRowView, implementer-typed
    versions = [row.details["to_version"] for row in rows]
    assert len(versions) == len(set(versions)), f"duplicated audit rows: {versions}"
    return {row.details["to_version"]: row for row in rows}


async def test_replacement_writes_one_exact_manifest_replaced_row(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    erin = await new_user(api, backend_settings, "erin", "admin")
    await arrange_membership(backend_settings, "erin", ACME)
    entity_id = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    UUID(entity_id)

    response = await put_manifest(api, erin, 1, with_model("mock-gen-large-v2"))
    assert response.status_code == 201, response.text

    rows = by_version(await audit_rows_for(backend_settings, entity_id))
    assert sorted(rows) == [1, 2]
    row = rows[2]
    assert row.action == "manifest_replaced"
    assert str(row.actor_id) == await user_id(api, erin)
    assert row.entity_type == "product"
    assert row.details == {
        "product_id": entity_id,
        "client_id": ACME,
        "from_version": 1,
        "to_version": 2,
        "changed_sections": ["bindings"],
    }
    assert row.client_ip is not None
    ipaddress.ip_address(str(row.client_ip).split("/")[0])
    assert row.created_at is not None


async def test_successive_replacements_write_one_row_per_version(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    entity_id = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    for base, model in ((1, "mock-gen-large-v2"), (2, "mock-gen-large-v3")):
        assert (await put_manifest(api, admin, base, with_model(model))).status_code == 201

    rows = by_version(await audit_rows_for(backend_settings, entity_id))
    assert sorted(rows) == [1, 2, 3]
    assert [rows[v].action for v in (1, 2, 3)] == [
        "manifest_created",
        "manifest_replaced",
        "manifest_replaced",
    ]
    assert [(rows[v].details["from_version"]) for v in (1, 2, 3)] == [None, 1, 2]
    admin_id = await user_id(api, admin)
    assert {str(row.actor_id) for row in rows.values()} == {admin_id}


async def test_entity_id_is_stable_per_product_and_distinct_between_products(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    kim = await new_user(api, backend_settings, "kim", "admin")
    await arrange_member_product(
        api, backend_settings, "globex", "portal", member="kim", member_token=kim
    )
    acme_entity = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    globex_entity = await product_entity_id(backend_settings, "globex", "portal")
    assert UUID(acme_entity) != UUID(globex_entity)

    document = (
        with_model("mock-gen-large-v2").replace("acme", "globex").replace("support-bot", "portal")
    )
    response = await put_manifest(api, kim, 1, document, client_id="globex", project_id="portal")
    assert response.status_code == 201, response.text

    product_rows = [
        row for row in await read_audit_rows(backend_settings) if row.entity_type == "product"
    ]
    assert sorted(str(row.entity_id) for row in product_rows) == sorted(
        [acme_entity, globex_entity, globex_entity]
    )
    for row in product_rows:
        assert row.details["product_id"] == str(row.entity_id)
    globex_rows = by_version(await audit_rows_for(backend_settings, globex_entity))
    assert globex_rows[1].action == "manifest_created"
    assert globex_rows[1].details == {
        "product_id": globex_entity,
        "client_id": "globex",
        "from_version": None,
        "to_version": 1,
        "changed_sections": [],
    }
    assert str(globex_rows[1].actor_id) == await user_id(api, await admin_token(api))
    assert globex_rows[2].details["client_id"] == "globex"
    assert str(globex_rows[2].actor_id) == await user_id(api, kim)


async def test_audit_details_hold_no_submitted_value_or_personal_data(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    quillon = await new_user(api, backend_settings, "quillon", "admin")
    await arrange_membership(backend_settings, "quillon", ACME)
    document = "# qzcommentmarker\n" + with_model("mock-qzfamilymarker-small-v1")
    response = await put_manifest(api, quillon, 1, document)
    assert response.status_code == 201, response.text

    rows = await read_audit_rows(backend_settings)
    assert any(row.action == "manifest_replaced" for row in rows)
    for row in rows:
        if row.entity_type != "product":
            continue
        assert set(row.details) == DETAIL_KEYS
        text = json.dumps(row.details)
        for forbidden in ("qzcommentmarker", "qzfamilymarker", "mock-", "quillon", "admin", "@"):
            assert forbidden not in text, (forbidden, row.details)

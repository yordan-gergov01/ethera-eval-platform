"""Sealed oracle: GET /api/v1/products/{client_id}/{project_id} returns the current Manifest.

Role: pins contract §2.2 of specs/001-product-registry/contract.md — the Manifest shape, the
  document returned character for character, bindings in document order, identifiers admitted
  at 1 and 64 characters, and one indistinguishable PRODUCT_NOT_FOUND for a missing Product, a
  non-member and an off-pattern segment (INV-REG-10, C-1).
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers through
  _contract_fixtures.py.
Key invariants: every 404 test first proves a 200 on the caller's own Product and asserts the
  code PRODUCT_NOT_FOUND, so a missing route cannot pass; the three 404 bodies of
  test_read_404_bodies_are_equal_for_missing_nonmember_and_off_pattern are compared after
  dropping only `instance` and `request_id`.
"""

from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.conftest import assert_problem, bearer
from tests.integration.registry._registry_oracle import (
    ACME,
    DEMO_DOCUMENT,
    LONGEST,
    SUPPORT_BOT,
    TOO_LONG,
    admin_token,
    arrange_member_product,
    assert_offset_timestamp,
    manifest_text,
    new_user,
    not_found_body,
    product_path,
    put_manifest,
    read_manifest,
)


async def test_read_requires_a_token(api: AsyncClient) -> None:
    admin = await admin_token(api)
    assert (await api.get(product_path(), headers=bearer(admin))).status_code == 200
    assert_problem(await api.get(product_path()), 401, "AUTHENTICATION_FAILED")
    response = await api.get(product_path(), headers=bearer("not-a-token"))
    assert_problem(response, 401, "INVALID_TOKEN")


async def test_read_returns_the_seeded_manifest(api: AsyncClient) -> None:
    response = await api.get(product_path(), headers=bearer(await admin_token(api)))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"client_id", "project_id", "manifest"}
    assert (body["client_id"], body["project_id"]) == (ACME, SUPPORT_BOT)
    manifest = body["manifest"]
    assert_offset_timestamp(manifest.pop("created_at"))
    document = manifest.pop("document")
    assert document.rstrip("\n") == DEMO_DOCUMENT.rstrip("\n")
    assert manifest == {
        "version": 1,
        "bindings": [{"role": "generation", "provider": "mock", "model": "mock-gen-small-v1"}],
        "allowed_providers": ["mock"],
        "created_by": "admin",
    }


async def test_read_unknown_product_is_product_not_found(api: AsyncClient) -> None:
    admin = await admin_token(api)
    await read_manifest(api, admin)
    for path in (product_path(ACME, "no-such-bot"), product_path("no-such-client", SUPPORT_BOT)):
        not_found_body(await api.get(path, headers=bearer(admin)))


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(product_path("Acme", SUPPORT_BOT), id="upper-case-client"),
        pytest.param(product_path(ACME, "Support-Bot"), id="upper-case-project"),
        pytest.param(product_path("-acme", SUPPORT_BOT), id="leading-hyphen"),
        pytest.param(product_path("acme-", SUPPORT_BOT), id="trailing-hyphen"),
        pytest.param(product_path(ACME, "support_bot"), id="underscore"),
        pytest.param(product_path(TOO_LONG, SUPPORT_BOT), id="client-65-chars"),
        pytest.param(product_path(ACME, TOO_LONG), id="project-65-chars"),
    ],
)
async def test_read_off_pattern_identifier_is_product_not_found(
    api: AsyncClient, path: str
) -> None:
    admin = await admin_token(api)
    await read_manifest(api, admin)
    not_found_body(await api.get(path, headers=bearer(admin)))


async def test_read_404_bodies_are_equal_for_missing_nonmember_and_off_pattern(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    lena = await new_user(api, backend_settings, "lena", "admin")
    await arrange_member_product(
        api, backend_settings, "globex", "portal", member="lena", member_token=lena
    )
    missing = not_found_body(await api.get(product_path("globex", "nope"), headers=bearer(lena)))
    nonmember = not_found_body(await api.get(product_path(), headers=bearer(lena)))
    off_pattern = not_found_body(
        await api.get(product_path("Globex", "portal"), headers=bearer(lena))
    )
    assert missing == nonmember == off_pattern


@pytest.mark.parametrize(
    ("client_id", "project_id"),
    [
        pytest.param(LONGEST, LONGEST, id="64-chars"),
        pytest.param("a", "b", id="1-char"),
        pytest.param("0-9", "a--b", id="digits-and-inner-hyphens"),
    ],
)
async def test_read_admits_identifiers_at_the_pattern_bounds(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
    client_id: str,
    project_id: str,
) -> None:
    await admin_token(api)
    reader = await new_user(api, backend_settings, "reader", "user")
    await arrange_member_product(
        api, backend_settings, client_id, project_id, member="reader", member_token=reader
    )


async def test_read_returns_bindings_in_document_order(api: AsyncClient) -> None:
    admin = await admin_token(api)
    bindings = [
        ("judge", "mock", "mock-judge-small-v1"),
        ("embedding", "mock", "mock-embed-small-v3"),
        ("generation", "mock", "mock-gen-small-v1"),
    ]
    response = await put_manifest(api, admin, 1, manifest_text(bindings=bindings))
    assert response.status_code == 201, response.text
    expected = [{"role": r, "provider": p, "model": m} for r, p, m in bindings]
    assert response.json()["bindings"] == expected
    manifest = await read_manifest(api, admin)
    assert manifest["bindings"] == expected
    assert manifest["allowed_providers"] == ["mock"]


async def test_read_returns_the_document_character_for_character(api: AsyncClient) -> None:
    admin = await admin_token(api)
    text = (
        "# Kundenservice — Prüfung \t\r\n"
        "product:   \r\n"
        "  client_id: 'acme'\r\n"
        '  project_id: "support-bot"\r\n'
        "\r\n"
        "bindings:\r\n"
        "  - {role: generation, provider: mock, model: mock-gen-large-v7}   # trailing\r\n"
        "allowed_providers: [mock]"
    )
    response = await put_manifest(api, admin, 1, text)
    assert response.status_code == 201, response.text
    assert response.json()["document"] == text
    assert (await read_manifest(api, admin))["document"] == text

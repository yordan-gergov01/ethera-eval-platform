"""Sealed oracle: a refusal (or an equal Manifest) consumes nothing.

Role: pins contract §4 of specs/001-product-registry/contract.md: after every refusal class
  (400, 401, 403, 404, 409, 422 VALIDATION_FAILED, 422 MANIFEST_INVALID) and after the 200 of
  an equal Manifest, no version is created, the current version and its document stay, no
  audit row is written, and every user's list and detail answers are unchanged.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers through
  _contract_fixtures.py.
Key invariants: the "before" state is asserted explicitly (version 1, the seeded binding, one
  audit row) so two equal 404 snapshots can never pass; every refused request carries a REAL
  change (a new model), so acceptance would show; an accepted replacement closes each test and
  must move the snapshot (anti-vacuity of the snapshot itself).
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient, Response

from tests.integration.conftest import assert_problem, bearer
from tests.integration.registry._contract_fixtures import arrange_membership
from tests.integration.registry._registry_oracle import (
    ACME,
    DEMO_DOCUMENT,
    SUPPORT_BOT,
    admin_token,
    assert_seeded_state,
    manifest_path,
    new_user,
    product_path,
    put_manifest,
    snapshot,
    with_model,
)

CHANGE = with_model("mock-gen-large-v9")
Tokens = dict[str, str]
Refusal = Callable[[AsyncClient, Tokens], Awaitable[Response]]


async def _malformed_json(api: AsyncClient, tokens: Tokens) -> Response:
    return await api.put(
        manifest_path(),
        content=b'{"base_version": 1, "document": "product',
        headers=bearer(tokens["admin"]) | {"Content-Type": "application/json"},
    )


async def _no_token(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, None, 1, CHANGE)


async def _bad_token(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, "not-a-token", 1, CHANGE)


async def _member_without_write(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, tokens["mira"], 1, CHANGE)


async def _admin_not_a_member(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, tokens["ivan"], 1, CHANGE)


async def _off_pattern_path(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, tokens["admin"], 1, CHANGE, client_id="ACME")


async def _stale_base(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, tokens["admin"], 2, CHANGE)


async def _unknown_field(api: AsyncClient, tokens: Tokens) -> Response:
    return await api.put(
        manifest_path(),
        json={"base_version": 1, "document": CHANGE, "force": True},
        headers=bearer(tokens["admin"]),
    )


async def _invalid_manifest(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, tokens["admin"], 1, with_model("mock-gen-large-latest"))


async def _equal_manifest(api: AsyncClient, tokens: Tokens) -> Response:
    return await put_manifest(api, tokens["admin"], 1, "# same Manifest\n" + DEMO_DOCUMENT)


REFUSALS: dict[str, tuple[Refusal, int, str | None]] = {
    "400-malformed-json": (_malformed_json, 400, "MALFORMED_REQUEST"),
    "401-no-token": (_no_token, 401, "AUTHENTICATION_FAILED"),
    "401-bad-token": (_bad_token, 401, "INVALID_TOKEN"),
    "403-member-without-write": (_member_without_write, 403, "PERMISSION_DENIED"),
    "404-admin-not-a-member": (_admin_not_a_member, 404, "PRODUCT_NOT_FOUND"),
    "404-off-pattern-path": (_off_pattern_path, 404, "PRODUCT_NOT_FOUND"),
    "409-stale-base": (_stale_base, 409, "MANIFEST_VERSION_CONFLICT"),
    "422-unknown-field": (_unknown_field, 422, "VALIDATION_FAILED"),
    "422-manifest-invalid": (_invalid_manifest, 422, "MANIFEST_INVALID"),
    "200-equal-manifest": (_equal_manifest, 200, None),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
async def test_refusal_changes_nothing_for_anyone(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
    case: str,
) -> None:
    tokens = {"admin": await admin_token(api)}
    tokens["mira"] = await new_user(api, backend_settings, "mira", "user")
    await arrange_membership(backend_settings, "mira", ACME)
    tokens["ivan"] = await new_user(api, backend_settings, "ivan", "admin")
    await assert_seeded_state(api, tokens["admin"], backend_settings)
    users = [tokens["admin"], tokens["mira"], tokens["ivan"]]
    paths = [product_path(ACME, SUPPORT_BOT)]
    before = await snapshot(api, backend_settings, users, paths)
    assert before[f"get-1-{paths[0]}"][0] == 200  # the member without write sees the Product
    assert before[f"get-2-{paths[0]}"][0] == 404  # the non-member admin does not

    refusal, status, code = REFUSALS[case]
    response = await refusal(api, tokens)

    if code is None:
        assert response.status_code == status, response.text
    else:
        assert_problem(response, status, code)
    assert await snapshot(api, backend_settings, users, paths) == before

    accepted = await put_manifest(api, tokens["admin"], 1, CHANGE)
    assert accepted.status_code == 201, accepted.text
    assert await snapshot(api, backend_settings, users, paths) != before

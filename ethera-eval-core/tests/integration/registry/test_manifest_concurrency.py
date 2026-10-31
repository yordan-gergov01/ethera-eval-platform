"""Sealed oracle: parallel replacements on one base version — one winner, gap-free versions.

Role: pins contract §3.2 "Concurrency" of specs/001-product-registry/contract.md (INV-REG-08,
  INV-REG-11): N parallel PUTs naming the same `base_version` give exactly one 201 and N-1
  `409 MANIFEST_VERSION_CONFLICT`, the winner's Manifest becomes current, version numbers stay
  gap-free across rounds, and each accepted version has exactly one audit row.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers `read_audit_rows` and
  `product_entity_id` through _contract_fixtures.py.
Key invariants: the requests really overlap (one `asyncio.gather` on the live app's client);
  the winner is identified by its response, never assumed; identical documents still yield one
  201 and conflicts only, because row 6 (version) is checked before row 8 (equality).
"""

import asyncio
from typing import Any

from httpx import AsyncClient, Response

from tests.integration.conftest import assert_problem
from tests.integration.registry._contract_fixtures import product_entity_id
from tests.integration.registry._registry_oracle import (
    ACME,
    SUPPORT_BOT,
    admin_token,
    audit_rows_for,
    put_manifest,
    read_manifest,
    with_model,
)

PARALLEL = 8
FAMILIES = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]


def winner_of(responses: list[Response]) -> int:
    """The index of the single 201; every other response is a version conflict."""
    accepted = [i for i, r in enumerate(responses) if r.status_code == 201]
    assert len(accepted) == 1, [r.status_code for r in responses]
    for index, response in enumerate(responses):
        if index != accepted[0]:
            assert_problem(response, 409, "MANIFEST_VERSION_CONFLICT")
    return accepted[0]


async def _round(api: AsyncClient, token: str, base: int, documents: list[str]) -> int:
    responses = await asyncio.gather(
        *(put_manifest(api, token, base, document) for document in documents)
    )
    winner = winner_of(list(responses))
    assert responses[winner].json()["version"] == base + 1
    return winner


async def test_parallel_replacements_on_one_base_accept_exactly_one(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    entity_id = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    documents = [with_model(f"mock-{family}-small-v1") for family in FAMILIES[:PARALLEL]]

    winner = await _round(api, admin, 1, documents)

    current = await read_manifest(api, admin)
    assert current["version"] == 2
    assert current["document"] == documents[winner]
    rows = await audit_rows_for(backend_settings, entity_id)
    assert sorted(row.details["to_version"] for row in rows) == [1, 2]
    [replaced] = [row for row in rows if row.action == "manifest_replaced"]
    assert (replaced.details["from_version"], replaced.details["to_version"]) == (1, 2)


async def test_versions_stay_gap_free_over_parallel_rounds(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    entity_id = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    for base in (1, 2, 3):
        documents = [with_model(f"mock-{family}-r{chr(96 + base)}-v1") for family in FAMILIES[:4]]
        await _round(api, admin, base, documents)

    assert (await read_manifest(api, admin))["version"] == 4
    rows = await audit_rows_for(backend_settings, entity_id)
    assert sorted(row.details["to_version"] for row in rows) == [1, 2, 3, 4]
    assert sorted(row.action for row in rows) == ["manifest_created"] + ["manifest_replaced"] * 3


async def test_parallel_identical_replacements_accept_one_and_conflict_the_rest(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    entity_id = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    document = with_model("mock-gen-large-v2")

    await _round(api, admin, 1, [document] * PARALLEL)

    assert (await read_manifest(api, admin))["version"] == 2
    rows = await audit_rows_for(backend_settings, entity_id)
    assert sorted(row.details["to_version"] for row in rows) == [1, 2]

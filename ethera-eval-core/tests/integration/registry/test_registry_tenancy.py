"""Sealed oracle: Client Memberships scope every registry endpoint; no role bypasses them.

Role: pins tenant isolation as observed through the API (contract §1, §2, §4 of
  specs/001-product-registry/contract.md; D-014, PP-002, INV-REG-10, INV-REG-13) for a member of
  Client A only, an admin who is a member of Client B only, and users without memberships, on
  list, read and replace; a non-member's 404 equals a missing Product's; a PUT to another
  Client's Product changes nothing there, as that Client's member sees it.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers through
  _contract_fixtures.py.
Key invariants: every arranged Product and membership is first proven through the API (the
  member's GET shows version 1), so a helper writing the wrong thing fails here instead of
  making isolation pass vacuously; the same `project_id` lives in two Clients.
"""

from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient

from tests.integration.conftest import assert_problem, bearer
from tests.integration.registry._contract_fixtures import product_entity_id, read_audit_rows
from tests.integration.registry._registry_oracle import (
    ACME,
    SUPPORT_BOT,
    admin_token,
    arrange_member_product,
    list_products,
    listed_ids,
    manifest_text,
    new_user,
    not_found_body,
    product_path,
    put_manifest,
    read_manifest,
)

GLOBEX = "globex"  # Client A
INITECH = "initech"  # Client B


@dataclass(frozen=True)
class World:
    admin: str  # seeded administrator, member of acme
    alice: str  # role user, member of globex only
    bruno: str  # role admin, member of initech only
    nora: str  # role user, no memberships
    ivan: str  # role admin, no memberships


async def arrange_world(api: AsyncClient, settings: Any) -> World:  # Any: opaque settings
    admin = await admin_token(api)
    alice = await new_user(api, settings, "alice", "user")
    bruno = await new_user(api, settings, "bruno", "admin")
    nora = await new_user(api, settings, "nora", "user")
    ivan = await new_user(api, settings, "ivan", "admin")
    await arrange_member_product(
        api, settings, GLOBEX, "portal", member="alice", member_token=alice
    )
    await arrange_member_product(
        api, settings, GLOBEX, SUPPORT_BOT, member="alice", member_token=alice, new_client=False
    )
    await arrange_member_product(
        api, settings, INITECH, "helpdesk", member="bruno", member_token=bruno
    )
    return World(admin, alice, bruno, nora, ivan)


ALL_PRODUCTS = [
    (ACME, SUPPORT_BOT),
    (GLOBEX, "portal"),
    (GLOBEX, SUPPORT_BOT),
    (INITECH, "helpdesk"),
]


async def test_list_shows_each_caller_only_its_clients(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    expected = {
        world.admin: [(ACME, SUPPORT_BOT)],
        world.alice: [(GLOBEX, "portal"), (GLOBEX, SUPPORT_BOT)],
        world.bruno: [(INITECH, "helpdesk")],
        world.nora: [],
        world.ivan: [],
    }
    for token, products in expected.items():
        listing = await list_products(api, token)
        assert listed_ids(listing) == products
        assert listing["total"] == len(products)


async def test_read_of_another_clients_product_equals_a_missing_product(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    visible = {
        world.admin: {(ACME, SUPPORT_BOT)},
        world.alice: {(GLOBEX, "portal"), (GLOBEX, SUPPORT_BOT)},
        world.bruno: {(INITECH, "helpdesk")},
        world.nora: set(),
        world.ivan: set(),
    }
    for token, own in visible.items():
        missing = not_found_body(
            await api.get(product_path("no-such-client", "no-such-bot"), headers=bearer(token))
        )
        for client_id, project_id in ALL_PRODUCTS:
            response = await api.get(product_path(client_id, project_id), headers=bearer(token))
            if (client_id, project_id) in own:
                assert response.status_code == 200, response.text
            else:
                assert not_found_body(response) == missing


async def test_same_project_id_in_two_clients_are_two_products(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    acme = await read_manifest(api, world.admin, ACME, SUPPORT_BOT)
    globex = await read_manifest(api, world.alice, GLOBEX, SUPPORT_BOT)
    assert "client_id: acme" in acme["document"]
    assert "client_id: globex" in globex["document"]
    acme_entity = await product_entity_id(backend_settings, ACME, SUPPORT_BOT)
    globex_entity = await product_entity_id(backend_settings, GLOBEX, SUPPORT_BOT)
    assert acme_entity != globex_entity


async def test_admin_of_another_client_cannot_replace_and_changes_nothing(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    target = {"client_id": GLOBEX, "project_id": "portal"}
    before = await read_manifest(api, world.alice, **target)
    rows_before = len(await read_audit_rows(backend_settings))
    attempts = [
        manifest_text(client_id=GLOBEX, project_id="portal", bindings=[("generation", "mock", m)])
        for m in ("mock-gen-large-v2", "mock-gen-small-latest")
    ]
    for token in (world.bruno, world.ivan):
        missing = not_found_body(
            await put_manifest(
                api,
                token,
                1,
                manifest_text(client_id=GLOBEX, project_id="no-such-bot"),
                client_id=GLOBEX,
                project_id="no-such-bot",
            )
        )
        for base, document in ((1, attempts[0]), (99, attempts[0]), (1, attempts[1])):
            response = await put_manifest(api, token, base, document, **target)
            assert not_found_body(response) == missing  # never 201, 409 or 422

    assert await read_manifest(api, world.alice, **target) == before
    assert len(await read_audit_rows(backend_settings)) == rows_before
    own = manifest_text(
        client_id=INITECH, project_id="helpdesk", bindings=[("generation", "mock", "mock-gen-x-v2")]
    )
    accepted = await put_manifest(
        api, world.bruno, 1, own, client_id=INITECH, project_id="helpdesk"
    )
    assert accepted.status_code == 201, accepted.text


async def test_user_without_write_is_refused_before_membership_is_revealed(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    document = manifest_text(client_id=GLOBEX, project_id="portal")
    for token in (world.alice, world.nora):
        for client_id, project_id in ((GLOBEX, "portal"), (INITECH, "helpdesk"), ("x", "y")):
            response = await put_manifest(
                api, token, 1, document, client_id=client_id, project_id=project_id
            )
            assert_problem(response, 403, "PERMISSION_DENIED")
    assert (await read_manifest(api, world.alice, GLOBEX, "portal"))["version"] == 1

"""Sealed oracle: Client Memberships scope both Dataset endpoints; no role bypasses them.

Role: pins tenant isolation of §2.1 to §2.2 and §4 of specs/002-demo-target-and-dataset/contract.md
  (D-014, D-022; the Product gate of slice 001 §2.2) for a member of Client A only, an admin who
  is a member of Client B only, and users with no memberships: a non-member's answer is the
  PRODUCT_NOT_FOUND of a missing Product, decided before anything about the Dataset (also for
  an unpublished version segment and an invalid identifier); the same `project_id` in two
  Clients holds two Datasets.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/evaluation/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _evaluation_oracle.py; the §6 helper `arrange_dataset_version`
  through _contract_fixtures.py; the slice 001 oracle vocabulary.
Key invariants: every arranged Dataset is first read back by its own member (a 200 with the
  arranged input), so a helper writing the wrong thing, or a missing route, fails here instead
  of making isolation pass vacuously; every refusal is compared with the missing Product's body
  AND carries the code PRODUCT_NOT_FOUND.
"""

from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient

from tests.integration.conftest import bearer
from tests.integration.evaluation._contract_fixtures import arrange_dataset_version
from tests.integration.evaluation._evaluation_oracle import (
    dataset_path,
    golden,
    read_summary,
    read_version,
    stable_problem,
    version_path,
)
from tests.integration.registry._registry_oracle import (
    ACME,
    SUPPORT_BOT,
    TOO_LONG,
    admin_token,
    arrange_member_product,
    new_user,
    not_found_body,
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


DATASETS = {
    (GLOBEX, SUPPORT_BOT): "Globex support question",
    (INITECH, "helpdesk"): "Initech helpdesk question",
}
PRODUCTS = [(ACME, SUPPORT_BOT), (GLOBEX, "portal"), *DATASETS]


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
    owners = {GLOBEX: alice, INITECH: bruno}
    for (client_id, project_id), question in DATASETS.items():
        number = await arrange_dataset_version(settings, client_id, project_id, [golden(question)])
        assert number == 1
        version = await read_version(api, owners[client_id], 1, client_id, project_id)
        assert [g["input"] for g in version["goldens"]] == [question]
    return World(admin, alice, bruno, nora, ivan)


def visible(world: World) -> dict[str, set[tuple[str, str]]]:
    """The Products whose Dataset each caller may read (portal has none: DATASET_NOT_FOUND)."""
    return {
        world.admin: {(ACME, SUPPORT_BOT)},
        world.alice: {(GLOBEX, SUPPORT_BOT), (GLOBEX, "portal")},
        world.bruno: {(INITECH, "helpdesk")},
        world.nora: set(),
        world.ivan: set(),
    }


async def test_dataset_of_another_client_equals_a_missing_product(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    for token, own in visible(world).items():
        headers = bearer(token)
        for build in (dataset_path, lambda c, p: version_path(1, c, p)):
            missing = not_found_body(await api.get(build("no-such-client", "bot"), headers=headers))
            for client_id, project_id in PRODUCTS:
                response = await api.get(build(client_id, project_id), headers=headers)
                if (client_id, project_id) not in own:
                    assert not_found_body(response) == missing, (client_id, project_id)
                elif (client_id, project_id) == (GLOBEX, "portal"):
                    stable_problem(response, 404, "DATASET_NOT_FOUND")  # member, no Dataset
                else:
                    assert response.status_code == 200, response.text


async def test_same_project_id_in_two_clients_holds_two_datasets(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    acme = await read_summary(api, world.admin, ACME, SUPPORT_BOT)
    globex = await read_summary(api, world.alice, GLOBEX, SUPPORT_BOT)
    assert acme["versions"][0]["golden_count"] == 19
    assert globex["versions"][0]["golden_count"] == 1
    globex_goldens = (await read_version(api, world.alice, 1, GLOBEX, SUPPORT_BOT))["goldens"]
    assert [g["input"] for g in globex_goldens] == [DATASETS[(GLOBEX, SUPPORT_BOT)]]
    acme_inputs = [g["input"] for g in (await read_version(api, world.admin, 1))["goldens"]]
    assert DATASETS[(GLOBEX, SUPPORT_BOT)] not in acme_inputs


async def test_product_gate_is_decided_before_the_version_segment(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    await read_version(api, world.bruno, 1, INITECH, "helpdesk")  # anchor: bruno's own 200
    for token in (world.alice, world.nora, world.ivan):
        headers = bearer(token)
        missing = not_found_body(
            await api.get(version_path(1, "no-such-client", "bot"), headers=headers)
        )
        for segment in ("abc", "0", "99999999999999999999", "2"):
            response = await api.get(version_path(segment, INITECH, "helpdesk"), headers=headers)
            assert not_found_body(response) == missing, segment


async def test_invalid_identifier_segments_are_a_missing_product(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    await read_summary(api, world.admin)  # anchor: the route answers this caller
    headers = bearer(world.admin)
    missing = not_found_body(await api.get(dataset_path("no-such-client", "bot"), headers=headers))
    for client_id, project_id in (("ACME", SUPPORT_BOT), (ACME, TOO_LONG), (ACME, "Support-Bot")):
        for path in (dataset_path(client_id, project_id), version_path(1, client_id, project_id)):
            assert not_found_body(await api.get(path, headers=headers)) == missing, path


async def test_refusals_change_nothing_for_the_owning_member(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    world = await arrange_world(api, backend_settings)
    before = await read_version(api, world.bruno, 1, INITECH, "helpdesk")
    summary = await read_summary(api, world.bruno, INITECH, "helpdesk")
    for token in (world.alice, world.ivan, world.nora):
        for path in (dataset_path(INITECH, "helpdesk"), version_path(1, INITECH, "helpdesk")):
            not_found_body(await api.get(path, headers=bearer(token)))
    assert await read_version(api, world.bruno, 1, INITECH, "helpdesk") == before
    assert await read_summary(api, world.bruno, INITECH, "helpdesk") == summary

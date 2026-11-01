"""Sealed oracle: Dataset versions are numbered without gaps, immutable, and refused uniformly.

Role: pins §2.1 to §2.2 and §3.2 (INV-EVAL-04) of specs/002-demo-target-and-dataset/contract.md:
  an arranged version reads back field by field; the summary lists every version ascending,
  `current_version` is the highest and `failure_type_counts` describes it with all six keys
  (C-201, C-202); version 1 is unchanged after version 2 except `is_current`; every segment that
  is not a published number is the same DATASET_VERSION_NOT_FOUND, never 422/500 (C-205); a
  Product without a Dataset answers DATASET_NOT_FOUND; the 401 answers.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/evaluation/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _evaluation_oracle.py; the §6 helper `arrange_dataset_version`
  through _contract_fixtures.py; the slice 001 helpers through
  tests/integration/registry/_registry_oracle.py.
Key invariants: every 404 is believed only after a 200 on the same Product's Dataset (or, for
  DATASET_NOT_FOUND, on the Product itself) by the same caller, so a missing route cannot pass
  as a refusal; every 401 is preceded by the authenticated 200 on the same path.
"""

from typing import Any

from httpx import AsyncClient

from tests.integration.conftest import assert_problem, bearer
from tests.integration.evaluation._contract_fixtures import arrange_dataset_version
from tests.integration.evaluation._evaluation_oracle import (
    FAILURE_TYPES,
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
    admin_token,
    arrange_member_product,
    assert_offset_timestamp,
    new_user,
)

REFUSED_SEGMENTS = (
    "0",
    "-1",
    "01",
    "1.0",
    "abc",
    "99999999999999999999",
    "+1",
    "1e0",
    "%201",
    "%EF%BC%91",  # FULLWIDTH DIGIT ONE, which int() would accept
    "2",  # beyond any version while only version 1 exists
)

V2_GOLDENS = [
    golden(
        "Can I return a gift?",
        "refund_rules",
        expected_decision="approve_refund",
        rule="Gift returns — doc refunds",
        context="Order 1042, delivered 3 days ago",
        expected_numbers=("4.90", "90"),
        owner="engineering",
    ),
    golden(
        "Is there a store in Lyon?",
        "out_of_docs",
        expected_decision="escalate",
        owner="support_content",
        unfixable_by_code=True,
    ),
    golden("Can I return it after 0 days?", "refund_rules", expected_decision="deny_refund"),
]


async def test_arranged_version_reads_back_field_by_field(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    await read_version(api, admin, 1)
    number = await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, V2_GOLDENS)
    assert number == 2
    version = await read_version(api, admin, 2)
    assert version["is_current"] is True
    assert_offset_timestamp(version["published_at"])
    assert version["goldens"] == [
        {"position": index, **arranged} for index, arranged in enumerate(V2_GOLDENS, start=1)
    ]


async def test_summary_follows_the_newest_version_with_all_six_counts(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    before = await read_summary(api, admin)
    assert before["current_version"] == 1
    assert await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, V2_GOLDENS) == 2
    summary = await read_summary(api, admin)
    version_two = await read_version(api, admin, 2)
    expected_counts = dict.fromkeys(FAILURE_TYPES, 0)
    expected_counts.update({"refund_rules": 2, "out_of_docs": 1})
    assert summary["current_version"] == 2
    assert summary["versions"] == [
        before["versions"][0],
        {"number": 2, "published_at": version_two["published_at"], "golden_count": 3},
    ]
    assert summary["failure_type_counts"] == expected_counts  # zeros included (C-202)

    assert await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, V2_GOLDENS[:1]) == 3
    summary = await read_summary(api, admin)
    assert summary["current_version"] == 3
    assert [v["number"] for v in summary["versions"]] == [1, 2, 3]
    assert [v["golden_count"] for v in summary["versions"]] == [19, 3, 1]
    assert summary["failure_type_counts"] == {
        name: 1 if name == "refund_rules" else 0 for name in FAILURE_TYPES
    }


async def test_published_version_never_changes_except_its_current_flag(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    before = await read_version(api, admin, 1)
    assert before["is_current"] is True
    assert await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, V2_GOLDENS) == 2
    after_two = await read_version(api, admin, 1)
    assert after_two["is_current"] is False
    assert (await read_version(api, admin, 2))["is_current"] is True
    assert {k: v for k, v in after_two.items() if k != "is_current"} == {
        k: v for k, v in before.items() if k != "is_current"
    }
    two = await read_version(api, admin, 2)
    assert await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, V2_GOLDENS) == 3
    assert await read_version(api, admin, 1) == after_two
    assert (await read_version(api, admin, 2))["is_current"] is False
    assert {k: v for k, v in (await read_version(api, admin, 2)).items() if k != "is_current"} == {
        k: v for k, v in two.items() if k != "is_current"
    }


async def test_every_unpublished_segment_is_the_same_version_not_found(
    api: AsyncClient,
) -> None:
    admin = await admin_token(api)
    await read_version(api, admin, 1)  # anchor: the route and the Dataset exist
    bodies = {}
    for segment in REFUSED_SEGMENTS:
        response = await api.get(version_path(segment), headers=bearer(admin))
        bodies[segment] = stable_problem(response, 404, "DATASET_VERSION_NOT_FOUND")
    assert all(body == bodies["0"] for body in bodies.values()), bodies


async def test_version_beyond_the_newest_is_not_found_after_arranging(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    assert await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, V2_GOLDENS) == 2
    await read_version(api, admin, 2)
    for segment in ("3", "02", "0"):
        response = await api.get(version_path(segment), headers=bearer(admin))
        stable_problem(response, 404, "DATASET_VERSION_NOT_FOUND")


async def test_product_without_dataset_is_dataset_not_found_on_both_endpoints(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    member = await new_user(api, backend_settings, "alice", "user")
    await arrange_member_product(
        api, backend_settings, "globex", "portal", member="alice", member_token=member
    )  # anchor: alice's GET of the Product answers 200
    summary = await api.get(dataset_path("globex", "portal"), headers=bearer(member))
    version = await api.get(version_path(1, "globex", "portal"), headers=bearer(member))
    assert stable_problem(summary, 404, "DATASET_NOT_FOUND") == stable_problem(
        version, 404, "DATASET_NOT_FOUND"
    )

    first = await arrange_dataset_version(
        backend_settings, "globex", "portal", [golden("A first question for globex")]
    )
    assert first == 1  # the Dataset is created at version 1
    summary_body = await read_summary(api, member, "globex", "portal")
    assert summary_body["current_version"] == 1
    assert summary_body["versions"][0]["golden_count"] == 1
    assert (await read_version(api, member, 1, "globex", "portal"))["is_current"] is True


async def test_missing_or_invalid_token_is_401_on_both_endpoints(api: AsyncClient) -> None:
    admin = await admin_token(api)
    for path in (dataset_path(), version_path(1)):
        response = await api.get(path, headers=bearer(admin))
        assert response.status_code == 200, response.text  # anchor: the route exists
        assert_problem(await api.get(path), 401, "AUTHENTICATION_FAILED")
        assert_problem(await api.get(path, headers=bearer("not-a-token")), 401, "INVALID_TOKEN")

"""Sealed oracle: the seeded Dataset of acme / support-bot, its 19 Goldens, its restarts.

Role: pins contract §3.1 (the seed: version 1 with exactly the 19 Goldens of §3.5, in order;
  create-only and idempotent), the §2.1 summary of the seed, the §3.5 table field by field as
  read through §2.2, and C-213 (the seed writes no audit row; the slice 001 seed's rows are
  unchanged) of specs/002-demo-target-and-dataset/contract.md.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/evaluation/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _evaluation_oracle.py; the slice 001 helpers `platform_app`,
  `read_audit_rows` through tests/integration/registry/_contract_fixtures.py; the §6 helper
  `arrange_dataset_version` through _contract_fixtures.py.
Key invariants: restart tests never take `api` — they enter `platform_app` twice in sequence;
  the audit test proves the Dataset exists (a 200) before it believes "no Dataset audit row",
  which would otherwise pass against the missing feature.
"""

from typing import Any

from httpx import AsyncClient

from tests.integration.evaluation._contract_fixtures import arrange_dataset_version
from tests.integration.evaluation._evaluation_oracle import (
    FAILURE_TYPES,
    SEEDED_COUNTS,
    SEEDED_GOLDENS,
    golden,
    read_summary,
    read_version,
)
from tests.integration.registry._contract_fixtures import platform_app, read_audit_rows
from tests.integration.registry._registry_oracle import (
    ACME,
    SUPPORT_BOT,
    admin_token,
    assert_offset_timestamp,
)


def expected_golden(row: tuple[int, str, str, str, str, tuple[str, ...]]) -> dict[str, Any]:
    position, input_text, decision, rule, failure_type, numbers = row
    gift_cards = position == 10
    return {
        "position": position,
        "input": input_text,
        "expected_decision": decision,
        "rule": rule,
        "failure_type": failure_type,
        "context": None,
        "expected_numbers": list(numbers),
        "owner": "support_content" if gift_cards else None,
        "unfixable_by_code": gift_cards,
    }


async def test_seed_publishes_version_one_with_the_nineteen_contract_goldens(
    api: AsyncClient,
) -> None:
    admin = await admin_token(api)
    version = await read_version(api, admin, 1)
    assert version["is_current"] is True
    assert_offset_timestamp(version["published_at"])
    assert len(version["goldens"]) == len(SEEDED_GOLDENS) == 19
    for actual, row in zip(version["goldens"], SEEDED_GOLDENS, strict=True):
        assert actual == expected_golden(row), f"Golden {row[0]}"


async def test_seed_summary_describes_version_one(api: AsyncClient) -> None:
    admin = await admin_token(api)
    summary = await read_summary(api, admin)
    version = await read_version(api, admin, 1)
    typed_counts = dict.fromkeys(FAILURE_TYPES, 0)
    for row in SEEDED_GOLDENS:
        typed_counts[row[4]] += 1
    assert typed_counts == SEEDED_COUNTS  # the §3.5 table and the §2.1 example agree
    assert summary == {
        "client_id": ACME,
        "project_id": SUPPORT_BOT,
        "current_version": 1,
        "versions": [{"number": 1, "published_at": version["published_at"], "golden_count": 19}],
        "failure_type_counts": SEEDED_COUNTS,
    }
    assert_offset_timestamp(summary["versions"][0]["published_at"])


async def test_restart_changes_nothing_in_the_seeded_dataset(
    backend_settings: Any,  # Any: opaque settings
) -> None:
    async with platform_app(backend_settings) as first:
        admin = await admin_token(first)
        summary = await read_summary(first, admin)
        version = await read_version(first, admin, 1)
        assert len(version["goldens"]) == 19

    async with platform_app(backend_settings) as second:
        admin = await admin_token(second)
        assert await read_summary(second, admin) == summary
        assert await read_version(second, admin, 1) == version


async def test_restart_keeps_an_arranged_version_and_seeds_nothing_again(
    backend_settings: Any,  # Any: opaque settings
) -> None:
    arranged = [golden("A restart-surviving question", "refund_rules")]
    async with platform_app(backend_settings) as first:
        admin = await admin_token(first)
        version_one = await read_version(first, admin, 1)
        number = await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, arranged)
        assert number == 2
        version_two = await read_version(first, admin, 2)

    async with platform_app(backend_settings) as second:
        admin = await admin_token(second)
        summary = await read_summary(second, admin)
        assert summary["current_version"] == 2
        assert [v["number"] for v in summary["versions"]] == [1, 2]
        assert [v["golden_count"] for v in summary["versions"]] == [19, 1]
        assert await read_version(second, admin, 2) == version_two
        after = await read_version(second, admin, 1)
        assert {k: v for k, v in after.items() if k != "is_current"} == {
            k: v for k, v in version_one.items() if k != "is_current"
        }


async def test_seed_and_arranged_versions_write_no_audit_row(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    assert (await read_summary(api, admin))["current_version"] == 1  # anchor: the seed ran
    rows = await read_audit_rows(backend_settings)
    assert [row.action for row in rows if row.entity_type == "product"] == ["manifest_created"]
    for row in rows:
        assert "dataset" not in f"{row.action} {row.entity_type}".lower(), row
        assert "golden" not in f"{row.action} {row.entity_type}".lower(), row

    number = await arrange_dataset_version(
        backend_settings, ACME, SUPPORT_BOT, [golden("An audit-free question")]
    )
    assert (await read_summary(api, admin))["current_version"] == number == 2
    assert len(await read_audit_rows(backend_settings)) == len(rows)

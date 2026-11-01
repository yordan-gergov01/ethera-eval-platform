"""The audit-detail guard: IDs and field names only, refused without quoting the value.

Role: pins backend.services.audit.service `check_details` (allowed values pass, free text,
  emails, documents, nested objects and floats are refused naming the key only),
  `normalise_client_ip` and the `entity_type` check of `write_audit_row`.
Used by: pytest (unit).
Depends on: backend.services.audit.service; no database (the refused `write_audit_row` raises
  before it reaches the repository).
Key invariants: a refusal never repeats the refused value; the guard fires before any write.
"""

from enum import StrEnum
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from backend.services.audit.service import (
    AuditDetailsError,
    AuditEntry,
    DetailValue,
    check_details,
    normalise_client_ip,
    write_audit_row,
)
from common_lib.audit import AuditAction

PRODUCT_ID = UUID("00000000-0000-4000-8000-000000000001")


class ProbeAction(StrEnum):
    """Stands in for the registry's members; an enum with members cannot be subclassed."""

    PROBE = "probe"


# write_audit_row reads only `.value`; the registry's own members arrive with their writer.
PROBE_ACTION = cast(AuditAction, ProbeAction.PROBE)


def test_check_details_ids_and_field_names_pass() -> None:
    details: dict[str, DetailValue] = {
        "product_id": PRODUCT_ID,
        "client_id": "acme",
        "from_version": None,
        "to_version": 2,
        "changed_sections": ["bindings"],
        "flag": True,
    }

    assert check_details(details) == {
        "product_id": str(PRODUCT_ID),
        "client_id": "acme",
        "from_version": None,
        "to_version": 2,
        "changed_sections": ["bindings"],
        "flag": True,
    }


SECRET = "marker-free text with spaces"


@pytest.mark.parametrize(
    "value",
    [
        SECRET,
        "admin@example.com",
        "product:\n  client_id: acme",
        "",
        "x" * 129,
        1.5,
        {"nested": "acme"},
        ["ok", SECRET],
    ],
)
def test_check_details_free_values_refused_without_quoting(value: Any) -> None:  # Any: probes
    with pytest.raises(AuditDetailsError) as refused:
        check_details({"note": value})

    assert "note" in str(refused.value)
    assert SECRET not in str(refused.value)
    assert "admin@example.com" not in str(refused.value)


@pytest.mark.parametrize("key", ["Bad", "with space", "1st", ""])
def test_check_details_keys_must_be_snake_case(key: str) -> None:
    with pytest.raises(AuditDetailsError):
        check_details({key: 1})


@pytest.mark.parametrize(
    ("address", "stored"),
    [
        ("127.0.0.1", "127.0.0.1"),
        ("2001:DB8::1", "2001:db8::1"),
        ("unknown", None),
        (None, None),
    ],
)
def test_normalise_client_ip_non_addresses_become_null(
    address: str | None, stored: str | None
) -> None:
    assert normalise_client_ip(address) == stored


@pytest.mark.parametrize("entity_type", ["Product", "has space", "x" * 65])
async def test_write_audit_row_bad_entity_type_refused_before_writing(entity_type: str) -> None:
    entry = AuditEntry(
        actor_id=uuid4(), action=PROBE_ACTION, entity_type=entity_type, entity_id=uuid4()
    )

    with pytest.raises(AuditDetailsError):
        await write_audit_row(object(), entry)  # type: ignore[arg-type]  # never reached

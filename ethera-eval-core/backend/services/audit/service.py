"""The audit writer: one audit row per audited change, in the change's own transaction.

Role: `AuditEntry` (what an audit row records) and `write_audit_row(connection, entry)`, which
  checks the details and inserts the row on the caller's transaction connection; `check_details`
  is the audit-detail guard of .claude/rules/privacy.md.
Used by: `backend.services.audit` (re-export), and through it the `backend` barrel (domain
  services, e.g. Manifest versions); tests/unit/backend/test_audit_service.py,
  tests/integration/test_audit.py.
Depends on: `backend.dal.audit.AuditRepository`, `backend.dal.tenancy.TransactionConnection`,
  `common_lib.audit.AuditAction`.
Key invariants: written on the SAME connection as the change it records, so both commit or
  neither does (.claude/rules/database.md). Details are IDs and field names only: keys are
  snake_case names; values are null, booleans, integers, UUIDs, or short tokens without spaces,
  `@` or line breaks (slugs, section names), or flat lists of those — anything else (free text,
  emails, documents, nested objects, floats) is refused BEFORE anything is written, and the
  refusal names the key, never the value. A client address that is not an IP address (e.g.
  `client_address`'s "unknown") is stored as null.
"""

import ipaddress
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.dal.audit import AuditRepository
from backend.dal.tenancy import TransactionConnection
from common_lib.audit import AuditAction

DETAIL_KEY = re.compile(r"[a-z][a-z0-9_]{0,63}")
# IDs, slugs and field names: no spaces, no '@', no line breaks, bounded length.
DETAIL_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
MAX_ENTITY_TYPE_LENGTH = 64

type DetailScalar = str | int | bool | UUID | None
type DetailValue = DetailScalar | Sequence[DetailScalar]


class AuditDetailsError(ValueError):
    """Audit details hold something other than IDs and field names (a programming error)."""


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """What one audit row records. `client_ip` is null for system actions such as seeds."""

    actor_id: UUID
    action: AuditAction
    entity_type: str
    entity_id: UUID
    details: Mapping[str, DetailValue] = field(default_factory=dict)
    client_ip: str | None = None


async def write_audit_row(connection: TransactionConnection, entry: AuditEntry) -> UUID:
    """Insert one audit row on the caller's transaction connection; return its ID."""
    if not DETAIL_KEY.fullmatch(entry.entity_type) or (
        len(entry.entity_type) > MAX_ENTITY_TYPE_LENGTH
    ):
        raise AuditDetailsError("entity_type must be a snake_case name")
    return await AuditRepository().insert(
        connection,
        actor_id=entry.actor_id,
        action=entry.action.value,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        details=check_details(entry.details),
        client_ip=normalise_client_ip(entry.client_ip),
    )


def check_details(details: Mapping[str, DetailValue]) -> dict[str, Any]:  # Any: JSON values
    """The details as JSON values, or AuditDetailsError naming the first offending key."""
    checked: dict[str, Any] = {}
    for key, value in details.items():
        if not isinstance(key, str) or not DETAIL_KEY.fullmatch(key):
            raise AuditDetailsError("audit detail keys are snake_case field names")
        if isinstance(value, list | tuple):
            checked[key] = [_scalar(key, item) for item in value]
        else:
            checked[key] = _scalar(key, value)
    return checked


def _scalar(key: str, value: object) -> str | int | bool | None:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str) and DETAIL_TOKEN.fullmatch(value):
        return value
    # Never the value itself: it may be exactly what must not be recorded.
    raise AuditDetailsError(f"audit detail {key!r} must hold IDs or field names only")


def normalise_client_ip(client_ip: str | None) -> str | None:
    """The address in canonical form, or None when it is absent or not an IP address."""
    if client_ip is None:
        return None
    try:
        return str(ipaddress.ip_address(client_ip))
    except ValueError:
        return None

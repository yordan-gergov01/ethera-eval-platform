"""Audit rows: the append-only evidence plane.

Role: the `AuditRow` model (table `audit_rows`): who (`actor`), what (`action`), which entity,
  details, the client's address and when.
Used by: `common_lib.models` (re-export), and through it `backend.dal.audit.repository`.
Depends on: Tortoise, `common_lib.models.user.User` (the actor).
Key invariants: append-only — the runtime role holds INSERT and SELECT only on this table,
  re-applied by the migration owner at every startup (`backend.core.startup`); a row is written
  in the SAME transaction as the change it records. `details` hold IDs and field names only,
  never personal data or Golden/Manifest text (checked by `backend.services.audit`). `action`
  values come from `common_lib.audit.AuditAction`. Schema changes need a new migration.
"""

from typing import Any
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

from common_lib.models.user import User

# Long enough for any IPv6 text form, including an IPv4-mapped one.
CLIENT_IP_MAX_LENGTH = 45


class AuditRow(Model):
    """One audited action. Never updated, never deleted."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    actor: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name=False, on_delete=fields.OnDelete.RESTRICT
    )
    action = fields.CharField(max_length=64)
    entity_type = fields.CharField(max_length=64)
    entity_id = fields.UUIDField()
    details: fields.JSONField[dict[str, Any]] = fields.JSONField()  # Any: JSON values
    client_ip = fields.CharField(max_length=CLIENT_IP_MAX_LENGTH, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "audit_rows"

"""Audit rows: the insert, on the caller's transaction.

Role: `AuditRepository.insert` writes one `audit_rows` row on the given connection.
Used by: `backend.dal.audit` (re-export), and through it `backend.services.audit.service`.
Depends on: Tortoise, `common_lib.models.AuditRow`, `backend.dal.tenancy.TransactionConnection`.
Key invariants: insert only — there is no update, delete or reader (no production caller in
  slice 001; tests read the table directly). The row goes through the caller's connection, so it
  commits or rolls back WITH the change it records.
"""

from typing import Any
from uuid import UUID

from backend.dal.tenancy import TransactionConnection
from common_lib.models import AuditRow


class AuditRepository:
    """Insert-only access to the audit table."""

    async def insert(
        self,
        connection: TransactionConnection,
        *,
        actor_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        details: dict[str, Any],  # Any: JSON values, already checked by the audit service
        client_ip: str | None,
    ) -> UUID:
        """Insert one row on `connection` and return its ID."""
        row = await AuditRow.create(
            using_db=connection,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            client_ip=client_ip,
        )
        return row.id

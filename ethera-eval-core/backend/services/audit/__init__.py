"""The audit writer.

Role: re-exports `AuditEntry`, `AuditDetailsError` and `write_audit_row` as the feature's public
  surface.
Used by: the `backend` barrel; tests/unit/backend/test_audit_service.py,
  tests/integration/test_audit.py.
Depends on: `backend.services.audit.service`.
Key invariants: none.
"""

from backend.services.audit.service import AuditDetailsError, AuditEntry, write_audit_row

__all__ = ["AuditDetailsError", "AuditEntry", "write_audit_row"]

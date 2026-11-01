"""Data access for audit rows.

Role: re-exports `AuditRepository` as the feature's public surface.
Used by: `backend.services.audit.service`.
Depends on: `backend.dal.audit.repository`.
Key invariants: none.
"""

from backend.dal.audit.repository import AuditRepository

__all__ = ["AuditRepository"]

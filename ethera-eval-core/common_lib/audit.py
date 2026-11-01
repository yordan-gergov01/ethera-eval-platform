"""The audit-action registry: every action an audit row may record.

Role: `AuditAction`, the append-only `StrEnum` of audited actions (manifest changes, baseline
  promotions, simulations, notification handling, account administration, as their slices
  arrive).
Used by: `backend.services.audit.service` (the type of an audit entry's action); domain modules
  through `common_lib` when they write audit rows.
Depends on: the standard library only.
Key invariants: APPEND-ONLY — a slice adds members at the end, never renames or removes one
  (values are stored in `audit_rows.action`). It starts empty: the first members arrive with
  their first writer (slice 001 wave 2, D-010). Every member must be referenced as
  `AuditAction.<NAME>` somewhere in the source
  (tests/architecture/test_registry_completeness.py
  `test_every_audit_action_is_referenced`). Values fit `audit_rows.action` (64 characters).
  ORM-free (import-linter).
"""

from enum import StrEnum


class AuditAction(StrEnum):
    """Every audited action. Values are stored: never rename one; append only."""

    # Slice 001: Manifest versions (INV-REG-11, PP-010).
    MANIFEST_CREATED = "manifest_created"
    MANIFEST_REPLACED = "manifest_replaced"

"""Data access for tenancy: the tenant transaction.

Role: re-exports `tenant_transaction`, `TransactionConnection` and `TENANTS_SETTING` as the
  feature's public surface.
Used by: the `backend` barrel; `backend.dal.audit.repository` (the connection type);
  tests/integration/test_tenancy.py.
Depends on: `backend.dal.tenancy.transaction`.
Key invariants: none.
"""

from backend.dal.tenancy.transaction import (
    TENANTS_SETTING,
    TransactionConnection,
    tenant_transaction,
)

__all__ = ["TENANTS_SETTING", "TransactionConnection", "tenant_transaction"]

"""The platform core's barrel: the only door through which domain modules reach the core.

Role: re-exports what `evals` may use from the core — the app factory, the module-mount type
  and its seed context, the database configuration the migration command line needs, the
  route dependencies (permissions, problem documentation, client address), the current-user
  value, the tenant transaction, the audit writer, and the Client and Membership functions.
  Appended to, never edited, as modules need more (spend arrives with its first caller in
  slice 003).
Used by: `evals.app`, `evals.MODULES`, `evals.migration_cli`, and the domain modules.
Depends on: `backend.main`, `backend.core.modules`, `backend.core.database`,
  `backend.core.settings`, `backend.api.dependencies` (permissions, rate_limit),
  `backend.api.errors`, `backend.services` (auth, audit, clients), `backend.dal.tenancy`.
Key invariants: `evals` imports `backend` only through this module (import-linter contract
  "The domain reaches the core only through its barrel"); nothing in `backend` imports
  `evals` (tests/integration/test_boot_without_evals.py), and nothing in `backend` imports this
  barrel (it would be circular). Every export has a consumer in `evals`
  (`test_backend_barrel_exports_only_what_evals_imports`).
"""

from backend.api.dependencies.permissions import require_permissions
from backend.api.dependencies.rate_limit import client_address
from backend.api.errors import documented_problem
from backend.core.database import tortoise_config
from backend.core.modules import ModuleMount, SeedContext
from backend.core.settings import BackendSettings, DatabaseSettings
from backend.dal.tenancy import TransactionConnection, tenant_transaction
from backend.main import create_app
from backend.services.audit import AuditEntry, write_audit_row
from backend.services.auth import CurrentUser
from backend.services.clients import ensure_client, ensure_membership, list_member_client_ids

__all__ = [
    "AuditEntry",
    "BackendSettings",
    "CurrentUser",
    "DatabaseSettings",
    "ModuleMount",
    "SeedContext",
    "TransactionConnection",
    "client_address",
    "create_app",
    "documented_problem",
    "ensure_client",
    "ensure_membership",
    "list_member_client_ids",
    "require_permissions",
    "tenant_transaction",
    "tortoise_config",
    "write_audit_row",
]

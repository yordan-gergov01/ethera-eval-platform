"""Tortoise ORM models. Only the backend imports this package; it owns the database.

Role: the core's model registry — Tortoise discovers the models by importing this module, so
  every model is re-exported here.
Used by: `backend.dal.roles.repository`, `backend.dal.users.repository`,
  `backend.dal.clients.repository`, `backend.dal.audit.repository`; Tortoise through the
  core app (`models`) in `backend.core.database.tortoise_config`;
  tests/unit/common_lib/test_models.py.
Depends on: `common_lib.models.role`, `common_lib.models.user`, `common_lib.models.client`,
  `common_lib.models.audit`.
Key invariants: the runner never imports it (import-linter "The runner has no database access";
  template_core D-011), and no other `common_lib` module may. A new core model must be
  re-exported here or Tortoise will not see it. Domain modules keep their models in their own
  app label (D-007).
"""

from common_lib.models.audit import AuditRow
from common_lib.models.client import Client, ClientMembership
from common_lib.models.role import PermissionRecord, Role
from common_lib.models.user import User

__all__ = ["AuditRow", "Client", "ClientMembership", "PermissionRecord", "Role", "User"]

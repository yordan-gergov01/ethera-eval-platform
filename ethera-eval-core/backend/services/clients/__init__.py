"""Clients and Client Memberships.

Role: re-exports `ensure_client`, `ensure_membership` and `list_member_client_ids` as the
  feature's public surface.
Used by: the `backend` barrel; tests/integration/test_clients.py.
Depends on: `backend.services.clients.service`.
Key invariants: none.
"""

from backend.services.clients.service import (
    ensure_client,
    ensure_membership,
    list_member_client_ids,
)

__all__ = ["ensure_client", "ensure_membership", "list_member_client_ids"]

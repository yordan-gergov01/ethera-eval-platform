"""Clients and Client Memberships: create-only, idempotent, and the caller's tenant set.

Role: `ensure_client`, `ensure_membership` (create whatever is missing, never touch what
  exists) and `list_member_client_ids` (the Client IDs a user may see, the input of
  `tenant_transaction`).
Used by: `backend.services.clients` (re-export), and through it the `backend` barrel (module
  seeds, domain services); tests/integration/test_clients.py.
Depends on: `backend.dal.clients.ClientRepository`.
Key invariants: create-only and idempotent, safe for every replica and every fixture; no API
  creates Clients or Memberships in slice 001 (PP-001, PP-002). No role bypasses Memberships:
  admins see only the Clients they are members of (PP-002). Member Client IDs are sorted.
"""

from uuid import UUID

from backend.dal.clients import ClientRepository


async def ensure_client(client_id: str) -> None:
    """Create the Client unless it exists."""
    await ClientRepository().create_client_if_missing(client_id)


async def ensure_membership(user_id: UUID, client_id: str) -> None:
    """Make the user a member of the Client unless it is one; NotFoundError if either is unknown."""
    await ClientRepository().create_membership_if_missing(user_id, client_id)


async def list_member_client_ids(user_id: UUID) -> tuple[str, ...]:
    """The Client IDs the user is a member of, sorted; empty for a user with none."""
    return await ClientRepository().list_member_client_ids(user_id)

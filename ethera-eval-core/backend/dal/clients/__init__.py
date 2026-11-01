"""Data access for Clients and Client Memberships.

Role: re-exports `ClientRepository` as the feature's public surface.
Used by: `backend.services.clients.service`.
Depends on: `backend.dal.clients.repository`.
Key invariants: none.
"""

from backend.dal.clients.repository import ClientRepository

__all__ = ["ClientRepository"]

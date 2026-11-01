"""Clients and Client Memberships.

Role: `ClientRepository`: create-only, idempotent inserts of Clients and Memberships, and the
  member Client IDs of a user.
Used by: `backend.dal.clients` (re-export), and through it `backend.services.clients.service`.
Depends on: Tortoise (`bulk_create` with `ignore_conflicts`), `common_lib.models` (`Client`,
  `ClientMembership`), `common_lib.errors.NotFoundError`.
Key invariants: create-only — nothing here updates or deletes. Inserts are
  `ON CONFLICT DO NOTHING`, so concurrent callers (two replicas, two fixtures) never fail on
  each other and an existing row is never touched. A membership of an unknown user or Client
  is a NotFoundError, never a silent no-op. Member Client IDs come back sorted, so the tenant
  set is deterministic. These tables carry no row security (D-022 Fork R1 = A).
"""

from datetime import UTC, datetime
from uuid import UUID

from tortoise.exceptions import IntegrityError

from common_lib.errors import NotFoundError
from common_lib.models import Client, ClientMembership

UNKNOWN_MEMBER_MESSAGE = "The user or the client does not exist."


class ClientRepository:
    """Create-only access to Clients and Client Memberships."""

    async def create_client_if_missing(self, client_id: str) -> None:
        """Insert the Client unless one with this `client_id` exists; never touches it."""
        await Client.bulk_create(
            [Client(client_id=client_id, created_at=datetime.now(UTC))], ignore_conflicts=True
        )

    async def create_membership_if_missing(self, user_id: UUID, client_id: str) -> None:
        """Insert the Membership unless it exists; an unknown user or Client raises."""
        membership = ClientMembership(
            user_id=user_id, client_id=client_id, created_at=datetime.now(UTC)
        )
        try:
            await ClientMembership.bulk_create([membership], ignore_conflicts=True)
        except IntegrityError as exc:
            # ON CONFLICT DO NOTHING covers the unique pair only; a foreign key still fails.
            raise NotFoundError(UNKNOWN_MEMBER_MESSAGE) from exc

    async def list_member_client_ids(self, user_id: UUID) -> tuple[str, ...]:
        """The Client IDs the user is a member of, sorted."""
        client_ids = await (
            ClientMembership.filter(user_id=user_id)
            .order_by("client_id")
            .values_list("client_id", flat=True)
        )
        return tuple(str(client_id) for client_id in client_ids)

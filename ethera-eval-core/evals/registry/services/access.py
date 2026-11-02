"""Which Products a caller may reach: the membership gate shared by every registry use case.

Role: `product_not_found()` (the one PRODUCT_NOT_FOUND error) and `member_client_ids_for(user_id,
  client_id, project_id)` — the member Client IDs a request on one Product runs with (its tenant
  transaction's set), or that error.
Used by: `evals.registry.services.products`, `.manifests`, `.lookup`; through the `evals.registry`
  barrel `evals.evaluation.services` (`member_client_ids_for`).
Depends on: the `backend` barrel (`list_member_client_ids`), `evals.registry.domain`
  (`is_identifier`), `common_lib.errors`.
Key invariants: a missing Product, a Client the caller is not a member of and an off-pattern
  path segment all raise the SAME error with the same message, so they are indistinguishable
  (INV-REG-10); no role bypasses Memberships (PP-002). The Client IDs of a single-Product
  request are that Product's Client only.
"""

from uuid import UUID

from backend import list_member_client_ids
from common_lib.errors import ErrorCode, NotFoundError
from evals.registry.domain import is_identifier

PRODUCT_NOT_FOUND_MESSAGE = "The Product does not exist."


def product_not_found() -> NotFoundError:
    """The answer for every Product the caller cannot see (INV-REG-10)."""
    return NotFoundError(PRODUCT_NOT_FOUND_MESSAGE, code=ErrorCode.PRODUCT_NOT_FOUND)


async def member_client_ids_for(user_id: UUID, client_id: str, project_id: str) -> tuple[str]:
    """The member Client IDs for one Product of `client_id`; PRODUCT_NOT_FOUND unless reachable."""
    if not (is_identifier(client_id) and is_identifier(project_id)):
        raise product_not_found()
    if client_id not in await list_member_client_ids(user_id):
        raise product_not_found()
    return (client_id,)

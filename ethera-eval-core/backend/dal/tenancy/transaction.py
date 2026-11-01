"""The tenant transaction: the one way a request's queries reach client-owned rows.

Role: `tenant_transaction(client_ids)` opens a transaction, sets `app.current_tenants` to the
  given Client IDs for that transaction only, and hands the transaction connection to the
  repositories; `TransactionConnection` is the connection type they receive.
Used by: `backend.dal.tenancy` (re-export), and through it the `backend` barrel (domain
  repositories and services); tests/integration/test_tenancy.py.
Depends on: Tortoise transactions.
Key invariants: the setting is written with `set_config(..., true)` INSIDE the transaction, so
  it is cleared at commit or rollback and never leaks to the next borrower of the pooled
  connection (D-022 Fork R1 = A). Row-security policies read it through the SQL function
  `app_current_tenants()` (migration 0004): an empty set and an unset setting both admit no row
  and never raise. Callers pass the yielded connection explicitly (`using_db=` /
  `connection.execute_query`) rather than relying on implicit transaction routing. A Client ID
  is a slug and never contains the separator.
"""

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

TENANTS_SETTING = "app.current_tenants"
SEPARATOR = ","

# The connection a repository receives inside a tenant transaction.
TransactionConnection = BaseDBAsyncClient


def encode_tenants(client_ids: Iterable[str]) -> str:
    """The setting's value: the distinct Client IDs, sorted, comma-separated."""
    if isinstance(client_ids, str):
        # A str is an iterable of characters: almost certainly a missing list.
        raise TypeError("client_ids must be a collection of Client IDs, not one string")
    tenants = sorted(set(client_ids))
    for client_id in tenants:
        if not client_id or SEPARATOR in client_id:
            raise ValueError("a Client ID is a non-empty slug without a comma")
    return SEPARATOR.join(tenants)


@asynccontextmanager
async def tenant_transaction(client_ids: Iterable[str]) -> AsyncIterator[TransactionConnection]:
    """A transaction whose row security admits exactly the rows of `client_ids`.

    An empty collection admits no row. Commit on normal exit, rollback on an exception.
    """
    tenants = encode_tenants(client_ids)
    async with in_transaction() as connection:
        await connection.execute_query(
            "SELECT set_config($1, $2, true)", [TENANTS_SETTING, tenants]
        )
        yield connection

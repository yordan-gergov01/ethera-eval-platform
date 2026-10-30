"""Database reachability check.

Role: `DatabaseProbe.ping`, a `SELECT 1` through the Tortoise connection pool.
Used by: `backend.dal.health` (re-export), and through it `backend.services.health.service`.
Depends on: Tortoise's `connections` (the `default` connection).
Key invariants: raises when the database cannot be reached; deciding what that means is the
  health service's job.
"""

from tortoise import connections


class DatabaseProbe:
    """Checks that the database answers a trivial query through the connection pool."""

    async def ping(self) -> None:
        """Run `SELECT 1`; raises if the database cannot be reached."""
        await connections.get("default").execute_query("SELECT 1")

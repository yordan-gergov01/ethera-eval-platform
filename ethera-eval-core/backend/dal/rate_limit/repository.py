"""Rate limit counters, shared by every backend replica through PostgreSQL.

Role: `RateLimitRepository` — counts a request in its window and reads the previous window in
  one statement, and deletes old windows.
Used by: `backend.dal.rate_limit` (re-export), and through it
  `backend.services.rate_limit.service`.
Depends on: Tortoise's raw connection; the unlogged `rate_limit_counters` table created by
  `migrations/0003_rate_limit_counters.py`.
Key invariants: one atomic `INSERT ... ON CONFLICT` per request, so concurrent requests from any
  replica never lose a count and no lock is held beyond the statement (template_core D-008).
  Counters are shared in PostgreSQL on purpose, not kept per replica.
"""

from dataclasses import dataclass

from tortoise import connections

# One statement: count this request in the current window and read the previous window.
# The upsert is atomic per row, so concurrent requests from any replica never lose a
# count, and no lock is held beyond the statement.
_INCREMENT = """
WITH current_window AS (
    INSERT INTO rate_limit_counters (key, window_start, count)
    VALUES ($1, $2, 1)
    ON CONFLICT (key, window_start)
    DO UPDATE SET count = rate_limit_counters.count + 1
    RETURNING count
)
SELECT
    (SELECT count FROM current_window) AS current,
    COALESCE(
        (SELECT count FROM rate_limit_counters WHERE key = $1 AND window_start = $3), 0
    ) AS previous
"""

_DELETE_BEFORE = "DELETE FROM rate_limit_counters WHERE window_start < $1"


@dataclass(frozen=True, slots=True)
class WindowCounts:
    """Requests counted in the current window (this one included) and the previous one."""

    current: int
    previous: int


class RateLimitRepository:
    """Every query on the rate limit counters."""

    async def increment(self, key: str, *, window_start: int, window_seconds: int) -> WindowCounts:
        """Count one request for `key` in the window starting at `window_start`."""
        [row] = await connections.get("default").execute_query_dict(
            _INCREMENT, [key, window_start, window_start - window_seconds]
        )
        return WindowCounts(current=row["current"], previous=row["previous"])

    async def delete_windows_before(self, window_start: int) -> int:
        """Remove windows that started before `window_start`; returns how many."""
        deleted: int
        deleted, _ = await connections.get("default").execute_query(_DELETE_BEFORE, [window_start])
        return deleted

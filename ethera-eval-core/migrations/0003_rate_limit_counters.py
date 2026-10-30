"""Core migration 0003: the unlogged rate limit counters table.

Role: creates `rate_limit_counters` (key, window start in Unix seconds, count) with raw SQL.
Used by: Tortoise's migration runner, via `backend.core.startup.apply_migrations` and
  `evals.migration_cli`; `backend.dal.rate_limit.repository` queries the table. No domain
  module migration exists yet; a module's first migration depends on the latest core revision
  it needs (D-007).
Depends on: 0002; Tortoise's `RunSQL`.
Key invariants: UNLOGGED on purpose: writes skip the write-ahead log, and a crash only empties
  the table, which resets the limits (template_core D-008). Raw SQL with no ORM model, because
  the ORM cannot declare an unlogged table. Never edited once applied.
"""

from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0002_users_roles_permissions")]

    initial = False

    operations = [
        # Request counters per key and fixed window (start in Unix seconds). UNLOGGED:
        # writes skip the write-ahead log, and a crash only empties the table, which
        # resets the limits. Raw SQL with no ORM model, because the ORM cannot declare an
        # unlogged table; the rate limit store queries it directly.
        ops.RunSQL(
            "CREATE UNLOGGED TABLE rate_limit_counters ("
            "key text NOT NULL, "
            "window_start bigint NOT NULL, "
            "count integer NOT NULL, "
            "PRIMARY KEY (key, window_start));",
            reverse_sql="DROP TABLE rate_limit_counters;",
        ),
    ]

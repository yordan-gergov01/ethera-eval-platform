"""Core migration 0001: enable the pgvector extension.

Role: the first revision of the core app (`models`); creates the `vector` extension if missing.
Used by: Tortoise's migration runner, via `backend.core.startup.apply_migrations` and
  `evals.migration_cli`; later revisions depend on it.
Depends on: Tortoise's migration operations (`RunSQL`).
Key invariants: the database init script already creates the extension as the superuser
  (template_core D-001); this keeps a database created any other way correct. Not reversed: the
  application role does not own the extension. Never edited once applied.
"""

from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    initial = True

    operations = [
        # The database init script already creates the extension as the superuser;
        # this keeps a database created any other way correct. Not reversed: the
        # application role does not own the extension.
        ops.RunSQL("CREATE EXTENSION IF NOT EXISTS vector;"),
    ]

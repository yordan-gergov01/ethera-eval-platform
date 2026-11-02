"""Data access for Datasets and their versions.

Role: `DatasetRepository` — `get_dataset`, `create_dataset`, `list_versions`, `create_version`
  — on the caller's tenant-transaction connection.
Used by: `evals.evaluation.repositories` (re-export), and through it `evals.evaluation.services`;
  tests/integration/evals/evaluation/test_repositories.py.
Depends on: Tortoise, `evals.evaluation.models` (`Dataset`, `DatasetVersion`),
  `evals.evaluation.repositories.records`, the `backend` barrel (`TransactionConnection`).
Key invariants: insert and read only — a version is never updated or deleted (INV-EVAL-04).
  Every query carries an explicit `client_id` filter, in the JOIN too, AND runs under row
  security on the given connection, so either alone keeps other Clients' rows out (D-014).
  Versions are listed ascending by number. Records, never ORM objects, leave this module.
"""

from typing import Any
from uuid import UUID

from backend import TransactionConnection
from evals.evaluation.models import Dataset, DatasetVersion
from evals.evaluation.repositories.records import DatasetRecord, VersionRecord

# Raw SQL: versions with their Golden counts (a grouped LEFT JOIN) are not expressible through
# the ORM's query builder without reverse relations. Bound parameters only; the JOIN repeats
# the Client filter (D-014).
LIST_VERSIONS_SQL = """
SELECT v.id, v.number, v.created_at, count(g.id) AS golden_count
FROM eval_dataset_versions v
LEFT JOIN eval_goldens g ON g.version_id = v.id AND g.client_id = v.client_id
WHERE v.dataset_id = $1 AND v.client_id = $2
GROUP BY v.id, v.number, v.created_at
ORDER BY v.number
"""


class DatasetRepository:
    """Datasets and versions of the Clients the connection's tenant set admits."""

    async def get_dataset(
        self, connection: TransactionConnection, client_id: str, product_id: UUID
    ) -> DatasetRecord | None:
        """The Product's Dataset, or None when it has none or it is not visible."""
        row = (
            await Dataset.filter(product_id=product_id, client_id=client_id)
            .using_db(connection)
            .first()
        )
        if row is None:
            return None
        return DatasetRecord(id=row.id, client_id=client_id)

    async def create_dataset(
        self, connection: TransactionConnection, client_id: str, product_id: UUID
    ) -> DatasetRecord:
        """Insert the Product's Dataset (one per Product: a second one is refused)."""
        row = await Dataset.create(using_db=connection, product_id=product_id, client_id=client_id)
        return DatasetRecord(id=row.id, client_id=client_id)

    async def list_versions(
        self, connection: TransactionConnection, dataset: DatasetRecord
    ) -> tuple[VersionRecord, ...]:
        """Every published version, ascending by number, with its Golden count."""
        rows = await connection.execute_query_dict(
            LIST_VERSIONS_SQL, [dataset.id, dataset.client_id]
        )
        return tuple(_version(row) for row in rows)

    async def create_version(
        self, connection: TransactionConnection, dataset: DatasetRecord, number: int
    ) -> UUID:
        """Insert version `number` of the Dataset; its ID, for its Goldens."""
        row = await DatasetVersion.create(
            using_db=connection,
            dataset_id=dataset.id,
            client_id=dataset.client_id,
            number=number,
        )
        version_id: UUID = row.id
        return version_id


def _version(row: dict[str, Any]) -> VersionRecord:  # Any: database row values
    return VersionRecord(
        id=row["id"],
        number=row["number"],
        published_at=row["created_at"],
        golden_count=int(row["golden_count"]),
    )

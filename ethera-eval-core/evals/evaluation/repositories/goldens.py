"""Data access for Goldens: a version's Goldens in order, their counts, and writing them.

Role: `GoldenRepository` — `list_goldens`, `count_failure_types`, `create_goldens` — on the
  caller's tenant-transaction connection.
Used by: `evals.evaluation.repositories` (re-export), and through it `evals.evaluation.services`;
  tests/integration/evals/evaluation/test_repositories.py.
Depends on: Tortoise, `evals.evaluation.models.GoldenRow`, `evals.evaluation.domain`,
  `evals.evaluation.repositories.records`, the `backend` barrel (`TransactionConnection`).
Key invariants: insert and read only — a Golden is never edited in place (INV-EVAL-04). Every
  query filters on `client_id` explicitly and runs under row security (D-014). Goldens are
  written at positions 1..n in the given order and read back in position order;
  `expected_numbers` are stored as the strings they were written as (C-203).
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from backend import TransactionConnection
from evals.evaluation.domain import Golden
from evals.evaluation.models import GoldenRow
from evals.evaluation.repositories.records import GoldenRecord

FIELDS = (
    "position",
    "input",
    "expected_decision",
    "rule",
    "failure_type",
    "context",
    "expected_numbers",
    "owner",
    "unfixable_by_code",
)


class GoldenRepository:
    """Goldens of the Clients the connection's tenant set admits."""

    async def list_goldens(
        self, connection: TransactionConnection, client_id: str, version_id: UUID
    ) -> tuple[GoldenRecord, ...]:
        """The version's Goldens in position order."""
        rows = await (
            GoldenRow.filter(version_id=version_id, client_id=client_id)
            .using_db(connection)
            .order_by("position")
            .values(*FIELDS)
        )
        return tuple(_record(row) for row in rows)

    async def count_failure_types(
        self, connection: TransactionConnection, client_id: str, version_id: UUID
    ) -> dict[str, int]:
        """How many of the version's Goldens have each failure type (absent types omitted)."""
        rows = await (
            GoldenRow.filter(version_id=version_id, client_id=client_id)
            .using_db(connection)
            .values_list("failure_type", flat=True)
        )
        counts: dict[str, int] = {}
        for failure_type in rows:
            counts[str(failure_type)] = counts.get(str(failure_type), 0) + 1
        return counts

    async def create_goldens(
        self,
        connection: TransactionConnection,
        client_id: str,
        version_id: UUID,
        goldens: Sequence[Golden],
    ) -> None:
        """Insert the Goldens of a new version at positions 1..n, in order."""
        await GoldenRow.bulk_create(
            [
                GoldenRow(
                    version_id=version_id,
                    client_id=client_id,
                    position=position,
                    input=golden.input,
                    expected_decision=golden.expected_decision.value,
                    rule=golden.rule,
                    failure_type=golden.failure_type.value,
                    context=golden.context,
                    expected_numbers=list(golden.expected_numbers),
                    owner=None if golden.owner is None else golden.owner.value,
                    unfixable_by_code=golden.unfixable_by_code,
                )
                for position, golden in enumerate(goldens, start=1)
            ],
            using_db=connection,
        )


def _record(row: dict[str, Any]) -> GoldenRecord:  # Any: database row values
    return GoldenRecord(
        position=row["position"],
        golden=Golden.of(
            input=row["input"],
            expected_decision=row["expected_decision"],
            rule=row["rule"],
            failure_type=row["failure_type"],
            context=row["context"],
            expected_numbers=row["expected_numbers"],
            owner=row["owner"],
            unfixable_by_code=row["unfixable_by_code"],
        ),
    )

"""Reading Datasets: a Product's Dataset summary and one published version in full.

Role: `get_dataset_summary(user, client_id, project_id)` and `get_dataset_version(user,
  client_id, project_id, segment)`, the read use cases behind
  `GET /api/v1/products/{client_id}/{project_id}/dataset` and `…/dataset/versions/{number}`
  (contract §2.1 to 2.2).
Used by: `evals.evaluation.services` (re-export), and through it `evals.evaluation.api`.
Depends on: the `backend` barrel (`CurrentUser`, `tenant_transaction`), the `evals.registry`
  barrel (`member_client_ids_for`, `get_visible_product`), `evals.evaluation.domain`,
  `evals.evaluation.repositories`, `common_lib.errors`.
Key invariants: checks run in the contract's order — the Product gate first (the registry's own
  PRODUCT_NOT_FOUND, so a non-member, a missing Product and an off-pattern identifier are one
  answer), then DATASET_NOT_FOUND, then the version segment (DATASET_VERSION_NOT_FOUND for any
  segment that is not a published number, C-205). Each refusal carries one fixed message,
  never the segment. The membership gate runs BEFORE the one tenant transaction, which is never
  nested (research finding 3). `is_current` is true only for the highest number; the counts
  describe the current version with all six failure types (C-202). Reads only: no audit row
  (C-213), and nothing of a Golden is logged.
"""

from dataclasses import dataclass
from datetime import datetime

from backend import CurrentUser, TransactionConnection, tenant_transaction
from common_lib.errors import ErrorCode, NotFoundError
from evals.evaluation.domain import FailureType, count_failure_types, parse_version_number
from evals.evaluation.repositories import (
    DatasetRecord,
    DatasetRepository,
    GoldenRecord,
    GoldenRepository,
    VersionRecord,
)
from evals.registry import get_visible_product, member_client_ids_for

DATASET_NOT_FOUND_MESSAGE = "The Product has no Dataset."
VERSION_NOT_FOUND_MESSAGE = "The Dataset has no such version."


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    """A Product's Dataset: every version and the failure-type counts of the current one."""

    client_id: str
    project_id: str
    versions: tuple[VersionRecord, ...]
    failure_type_counts: dict[FailureType, int]

    @property
    def current_version(self) -> int:
        return self.versions[-1].number


@dataclass(frozen=True, slots=True)
class DatasetVersionDetails:
    """One published version with its Goldens in order."""

    client_id: str
    project_id: str
    number: int
    published_at: datetime
    is_current: bool
    goldens: tuple[GoldenRecord, ...]


def dataset_not_found() -> NotFoundError:
    return NotFoundError(DATASET_NOT_FOUND_MESSAGE, code=ErrorCode.DATASET_NOT_FOUND)


def version_not_found() -> NotFoundError:
    return NotFoundError(VERSION_NOT_FOUND_MESSAGE, code=ErrorCode.DATASET_VERSION_NOT_FOUND)


async def _member_dataset(
    connection: TransactionConnection, client_id: str, project_id: str
) -> tuple[DatasetRecord, tuple[VersionRecord, ...]]:
    """The Product's Dataset and its versions, or the Product's or the Dataset's 404."""
    product = await get_visible_product(connection, client_id, project_id)
    dataset = await DatasetRepository().get_dataset(connection, product.client_id, product.id)
    if dataset is None:
        raise dataset_not_found()
    versions = await DatasetRepository().list_versions(connection, dataset)
    if not versions:  # a Dataset is created with its version 1, in one transaction
        raise dataset_not_found()
    return dataset, versions


async def get_dataset_summary(user: CurrentUser, client_id: str, project_id: str) -> DatasetSummary:
    """Every version of the Product's Dataset and the counts of its current version."""
    client_ids = await member_client_ids_for(user.id, client_id, project_id)
    async with tenant_transaction(client_ids) as connection:
        dataset, versions = await _member_dataset(connection, client_id, project_id)
        counts = await GoldenRepository().count_failure_types(
            connection, dataset.client_id, versions[-1].id
        )
    return DatasetSummary(client_id, project_id, versions, count_failure_types(counts))


async def get_dataset_version(
    user: CurrentUser, client_id: str, project_id: str, segment: str
) -> DatasetVersionDetails:
    """The published version a path segment names, with its Goldens in position order."""
    client_ids = await member_client_ids_for(user.id, client_id, project_id)
    async with tenant_transaction(client_ids) as connection:
        dataset, versions = await _member_dataset(connection, client_id, project_id)
        number = parse_version_number(segment)
        version = next((v for v in versions if v.number == number), None)
        if version is None:
            raise version_not_found()
        goldens = await GoldenRepository().list_goldens(connection, dataset.client_id, version.id)
    return DatasetVersionDetails(
        client_id=client_id,
        project_id=project_id,
        number=version.number,
        published_at=version.published_at,
        is_current=version.number == versions[-1].number,
        goldens=goldens,
    )

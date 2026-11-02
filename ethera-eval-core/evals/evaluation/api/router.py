"""`/api/v1/products/{client_id}/{project_id}/dataset` routes: the summary and one version.

Role: the evaluation module's thin HTTP layer (contract §2.1 to 2.2); each route declares its
  Permission and calls one service.
Used by: `evals.evaluation.module` (the router of the module's `ModuleMount`, mounted under
  `/api/v1` by the core).
Depends on: the `backend` barrel (`CurrentUser`, `documented_problem`, `require_permissions`),
  `common_lib.permissions`, `evals.evaluation.services`, `evals.evaluation.api.schemas`.
Key invariants: both routes need `products:read` (PP-209): reading a Dataset is part of reading
  a Product. Path segments, `{number}` included, are plain strings on purpose: the service
  decides, so an off-pattern identifier is the Product's 404 and any segment that is not a
  published number is DATASET_VERSION_NOT_FOUND — never a 422 or a 500 (C-205, FIX-004).
  Tagged `datasets`, apart from the registry's `products` routes under the same prefix (R-207).
"""

from typing import Annotated, Any

from fastapi import APIRouter, status

from backend import CurrentUser, documented_problem, require_permissions
from common_lib.permissions import Permission
from evals.evaluation.api.schemas import DatasetSummaryResponse, DatasetVersionResponse
from evals.evaluation.services import get_dataset_summary, get_dataset_version

router = APIRouter(prefix="/products", tags=["datasets"])

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: documented_problem("Missing or invalid token"),
    status.HTTP_403_FORBIDDEN: documented_problem("Missing permission"),
    status.HTTP_404_NOT_FOUND: documented_problem(
        "No such Product (or the caller is not a member of its Client), no Dataset, "
        "or no such version"
    ),
}

ProductsReader = Annotated[CurrentUser, require_permissions(Permission.PRODUCTS_READ)]


@router.get(
    "/{client_id}/{project_id}/dataset",
    response_model=DatasetSummaryResponse,
    responses=RESPONSES,
)
async def read_dataset_summary(
    user: ProductsReader, client_id: str, project_id: str
) -> DatasetSummaryResponse:
    """The Product's Dataset: every version, and the failure-type counts of the current one."""
    return DatasetSummaryResponse.of(await get_dataset_summary(user, client_id, project_id))


@router.get(
    "/{client_id}/{project_id}/dataset/versions/{number}",
    response_model=DatasetVersionResponse,
    responses=RESPONSES,
)
async def read_dataset_version(
    user: ProductsReader, client_id: str, project_id: str, number: str
) -> DatasetVersionResponse:
    """One published version of the Product's Dataset with its Goldens in order."""
    details = await get_dataset_version(user, client_id, project_id, number)
    return DatasetVersionResponse.of(details)

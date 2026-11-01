"""`/api/v1/products` routes: list Products, read one, replace its Manifest (contract §2).

Role: the registry's thin HTTP layer; each route declares its Permission and calls one service.
Used by: `evals.registry.module` (the router of the registry's `ModuleMount`, mounted under
  `/api/v1` by the core).
Depends on: the `backend` barrel (`CurrentUser`, `client_address`, `documented_problem`,
  `require_permissions`), `common_lib.permissions`, `evals.registry.services`,
  `evals.registry.api.schemas`.
Key invariants: the PUT answers in the order of contract §2.3 — malformed JSON (400) and the
  token (401) are the platform's, the Permission (403) is a route dependency and so precedes
  body validation (422), and the path is checked by the service, so an off-pattern segment is
  the same 404 as a missing Product (INV-REG-10), never a 422. 201 for a new version, 200 for
  an equal Manifest. Path segments are plain strings on purpose.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response, status

from backend import CurrentUser, client_address, documented_problem, require_permissions
from common_lib.permissions import Permission
from evals.registry.api.schemas import (
    ManifestReplace,
    ManifestResponse,
    ProductPageResponse,
    ProductResponse,
)
from evals.registry.services import get_product, list_products, replace_manifest

router = APIRouter(prefix="/products", tags=["products"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

FORBIDDEN: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: documented_problem("Missing or invalid token"),
    status.HTTP_403_FORBIDDEN: documented_problem("Missing permission"),
}
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: documented_problem(
        "No such Product, or the caller is not a member of its Client"
    )
}

ProductsReader = Annotated[CurrentUser, require_permissions(Permission.PRODUCTS_READ)]
ManifestsWriter = Annotated[CurrentUser, require_permissions(Permission.MANIFESTS_WRITE)]


@router.get("", response_model=ProductPageResponse, responses=FORBIDDEN)
async def list_products_route(
    user: ProductsReader,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductPageResponse:
    """The Products of every Client you are a member of, by `client_id` then `project_id`."""
    page = await list_products(user, limit=limit, offset=offset)
    return ProductPageResponse.of(page, limit=limit, offset=offset)


@router.get(
    "/{client_id}/{project_id}",
    response_model=ProductResponse,
    responses=FORBIDDEN | NOT_FOUND,
)
async def read_product(user: ProductsReader, client_id: str, project_id: str) -> ProductResponse:
    """One Product with its current Manifest."""
    return ProductResponse.of(await get_product(user, client_id, project_id))


@router.put(
    "/{client_id}/{project_id}/manifest",
    response_model=ManifestResponse,
    status_code=status.HTTP_201_CREATED,
    responses=FORBIDDEN
    | NOT_FOUND
    | {
        status.HTTP_200_OK: {"description": "Equal to the current Manifest; nothing changed"},
        status.HTTP_409_CONFLICT: documented_problem("`base_version` is not the current version"),
    },
)
async def replace_product_manifest(
    actor: ManifestsWriter,
    client_id: str,
    project_id: str,
    replacement: ManifestReplace,
    request: Request,
    response: Response,
) -> ManifestResponse:
    """Replace the Manifest; an invalid one is a 422 `MANIFEST_INVALID` listing every problem."""
    result = await replace_manifest(
        actor,
        client_id,
        project_id,
        base_version=replacement.base_version,
        document=replacement.document,
        client_ip=client_address(request),
    )
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return ManifestResponse.of(result.manifest)

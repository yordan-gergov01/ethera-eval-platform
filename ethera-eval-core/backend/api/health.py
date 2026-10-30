"""`GET /health`: used by the container health check. Outside `/api/v1`, no auth.

Role: the liveness/readiness route; 200 when the database is reachable, 503 otherwise.
Used by: `backend.main` (mounted at the root); the backend container's health check.
Depends on: `backend.services.health` (`HealthService`, `build_health_service`).
Key invariants: outside `/api/v1`, so it is neither authenticated nor rate limited
  (template_core D-008); its access lines are logged at debug level by
  `backend.api.middleware`.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from backend.services.health import HealthService, build_health_service

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(
    response: Response,
    service: Annotated[HealthService, Depends(build_health_service)],
) -> HealthResponse:
    """Return 200 when the database is reachable, 503 otherwise."""
    if await service.database_ok():
        return HealthResponse(status="ok", database="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="unavailable", database="unavailable")

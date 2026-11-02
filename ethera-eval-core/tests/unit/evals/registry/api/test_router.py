"""Every registry route, on the full platform app, requires exactly its declared Permission.

Role: pins evals.registry.api.router as mounted by `evals.app.create_app`: list and read require
  `products:read`, the Manifest replacement requires `manifests:write` (PP-003), each as an
  OpenAPI security scope (what `require_permissions` declares) and as behaviour — a caller
  without the Permission gets 403 PERMISSION_DENIED before anything else runs, on routes no
  built-in role can be refused (contract §1: both roles hold `products:read`).
Used by: pytest (unit; no database: the current-user dependency is overridden).
Depends on: `evals.app.create_app`; backend.api.dependencies.auth `get_current_user` and
  backend.api.dependencies.rate_limit `limit_requests` (overridden); fake settings.
Key invariants: the expected table is written by hand, so a route that loses or changes its
  Permission fails here; the behavioural check uses a caller holding every OTHER Permission.
  The scan covers the registry's own routes — those tagged `products` — since the evaluation
  module mounts its Dataset routes under the same prefix (slice 002, R-207); that no
  `/api/v1/products` route escapes both modules' tables is pinned by
  `test_every_products_route_belongs_to_exactly_one_module` in
  tests/unit/evals/evaluation/api/test_router.py.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend import BackendSettings, CurrentUser
from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.rate_limit import limit_requests
from common_lib.permissions import Permission
from evals.app import create_app

SETTINGS = {
    "db_name": "unit_tests",
    "db_user": "unit_tests",
    "db_password": "test-only-not-a-secret",
    "db_owner_user": "unit_tests_owner",
    "db_owner_password": "test-only-not-a-secret",
    "jwt_secret": "test-only-not-a-secret-signing-key-32-bytes-long",
    "admin_username": "admin",
    "admin_email": "admin@example.com",
    "admin_password": "test-only-admin-password",
    "rabbitmq_vhost": "unit_tests",
    "rabbitmq_user": "unit_tests",
    "rabbitmq_password": "test-only-not-a-secret",
}
EXPECTED = {
    ("get", "/api/v1/products"): Permission.PRODUCTS_READ,
    ("get", "/api/v1/products/{client_id}/{project_id}"): Permission.PRODUCTS_READ,
    ("put", "/api/v1/products/{client_id}/{project_id}/manifest"): Permission.MANIFESTS_WRITE,
}
CALLS = {
    Permission.PRODUCTS_READ: [("GET", "/api/v1/products"), ("GET", "/api/v1/products/a/b")],
    Permission.MANIFESTS_WRITE: [("PUT", "/api/v1/products/a/b/manifest")],
}


def platform_app() -> FastAPI:
    return create_app(BackendSettings.model_validate(SETTINGS))


def test_every_registry_route_declares_its_permission() -> None:
    schema = platform_app().openapi()
    declared = {
        (method, path): {
            scope
            for requirement in operation.get("security", [])
            for scopes in requirement.values()
            for scope in scopes
        }
        for path, methods in schema["paths"].items()
        for method, operation in methods.items()
        if "products" in operation.get("tags", [])
    }

    assert declared == {key: {permission.value} for key, permission in EXPECTED.items()}


@pytest.fixture
async def without(request: pytest.FixtureRequest) -> AsyncIterator[AsyncClient]:
    """The platform app with a caller holding every Permission except `request.param`."""
    missing: Permission = request.param
    app = platform_app()

    async def caller() -> CurrentUser:
        return CurrentUser.model_validate(
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "username": "probe",
                "email": "probe@example.com",
                "full_name": "Probe",
                "role": "probe",
                "permissions": frozenset(set(Permission) - {missing}),
            }
        )

    async def no_limit() -> None:
        return None

    app.dependency_overrides[get_current_user] = caller
    app.dependency_overrides[limit_requests] = no_limit
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.parametrize("without", list(CALLS), indirect=True)
async def test_registry_route_without_its_permission_is_403(
    without: AsyncClient, request: pytest.FixtureRequest
) -> None:
    missing: Permission = request.node.callspec.params["without"]
    for method, path in CALLS[missing]:
        body = {"base_version": 0} if method == "PUT" else None
        response = await without.request(method, path, json=body)

        assert response.status_code == 403, (method, path)
        assert response.json()["code"] == "PERMISSION_DENIED"

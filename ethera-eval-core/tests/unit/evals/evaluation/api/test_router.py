"""Every Dataset route, on the full platform app, requires exactly its declared Permission.

Role: pins evals.evaluation.api.router as mounted by `evals.app.create_app`: both Dataset routes
  require `products:read` (PP-209), as an OpenAPI security scope and as behaviour — a caller
  without it gets 403 PERMISSION_DENIED before anything else runs (no built-in role lacks it,
  contract §2). Also pins R-207: every `/api/v1/products` operation belongs to exactly one
  module's table, the registry's (tag `products`) or the evaluation module's (tag `datasets`).
Used by: pytest (unit; no database: the current-user dependency is overridden).
Depends on: `evals.app.create_app`; backend.api.dependencies.auth `get_current_user` and
  backend.api.dependencies.rate_limit `limit_requests` (overridden); fake settings.
Key invariants: the expected table is written by hand, so a route that loses or changes its
  Permission fails here; the behavioural check uses a caller holding every OTHER Permission and
  path segments that would otherwise be a 404, so only the Permission can explain the 403.
  `test_every_products_route_belongs_to_exactly_one_module` keeps the registry's narrowed scan
  (tests/unit/evals/registry/api/test_router.py) from letting a route escape both tables.
"""

from collections.abc import AsyncIterator
from typing import Any

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
SUMMARY = "/api/v1/products/{client_id}/{project_id}/dataset"
VERSION = "/api/v1/products/{client_id}/{project_id}/dataset/versions/{number}"
EXPECTED = {
    ("get", SUMMARY): Permission.PRODUCTS_READ,
    ("get", VERSION): Permission.PRODUCTS_READ,
}
REGISTRY_OPERATIONS = {
    ("get", "/api/v1/products"),
    ("get", "/api/v1/products/{client_id}/{project_id}"),
    ("put", "/api/v1/products/{client_id}/{project_id}/manifest"),
}
CALLS = ["/api/v1/products/a/b/dataset", "/api/v1/products/a/b/dataset/versions/abc"]


def platform_app() -> FastAPI:
    return create_app(BackendSettings.model_validate(SETTINGS))


def _operations(tag: str | None = None) -> dict[tuple[str, str], Any]:  # Any: OpenAPI values
    schema = platform_app().openapi()
    return {
        (method, path): operation
        for path, methods in schema["paths"].items()
        if path.startswith("/api/v1/products")
        for method, operation in methods.items()
        if tag is None or tag in operation.get("tags", [])
    }


def test_every_dataset_route_declares_its_permission() -> None:
    declared = {
        key: {
            scope
            for requirement in operation.get("security", [])
            for scopes in requirement.values()
            for scope in scopes
        }
        for key, operation in _operations("datasets").items()
    }

    assert declared == {key: {permission.value} for key, permission in EXPECTED.items()}


def test_every_products_route_belongs_to_exactly_one_module() -> None:
    operations = _operations()
    registry = set(_operations("products"))
    datasets = set(_operations("datasets"))

    assert registry == REGISTRY_OPERATIONS
    assert datasets == set(EXPECTED)
    assert registry.isdisjoint(datasets)
    assert set(operations) == registry | datasets


@pytest.fixture
async def without_products_read() -> AsyncIterator[AsyncClient]:
    """The platform app with a caller holding every Permission except `products:read`."""
    app = platform_app()

    async def caller() -> CurrentUser:
        return CurrentUser.model_validate(
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "username": "probe",
                "email": "probe@example.com",
                "full_name": "Probe",
                "role": "probe",
                "permissions": frozenset(set(Permission) - {Permission.PRODUCTS_READ}),
            }
        )

    async def no_limit() -> None:
        return None

    app.dependency_overrides[get_current_user] = caller
    app.dependency_overrides[limit_requests] = no_limit
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_dataset_route_without_products_read_is_403(
    without_products_read: AsyncClient,
) -> None:
    for path in CALLS:
        response = await without_products_read.get(path)

        assert response.status_code == 403, path
        assert response.json()["code"] == "PERMISSION_DENIED"

"""Mechanical guard: every entry of the core's shared registries is wired, none is dead.

Role: the insurance tier for the append-only registries (Bible, cross-cutting surfaces):
  every `Permission` is granted to a role and required by at least one route; every
  `ErrorCode` is referenced as `ErrorCode.<NAME>` somewhere (a default code of an exception
  class, a raise, or the HTTP mapping) — member definitions never use that prefix. Audit
  actions join this guard when the audit table exists (docs/DECISIONS.md D-009, D-010).
Used by: pytest (unit-level; builds the app without a database).
Depends on: `evals.app.create_app` (the composed app, so module routes count too), the
  OpenAPI security scopes FastAPI derives from `require_permissions`, and a source scan.
Key invariants: a registry entry with no consumer fails the build (no dead seams); the
  negative cases prove both checks fire.
"""

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from backend.core.settings import BackendSettings
from common_lib.errors import ErrorCode
from common_lib.permissions import DEFAULT_ROLE_GRANTS, Permission
from evals.app import create_app

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PACKAGES = ("backend", "common_lib", "runner", "evals")
# Fake values; the app is only built for its OpenAPI document and never connects.
UNIT_SETTINGS = {
    "db_name": "unit_tests",
    "db_user": "unit_tests",
    "db_password": "test-only-not-a-secret",
    "jwt_secret": "test-only-not-a-secret-signing-key-32-bytes-long",
    "admin_username": "admin",
    "admin_email": "admin@example.com",
    "admin_password": "test-only-admin-password",
    "rabbitmq_vhost": "unit_tests",
    "rabbitmq_user": "unit_tests",
    "rabbitmq_password": "test-only-not-a-secret",
}


def required_scopes(schema: dict[str, Any]) -> set[str]:
    scopes: set[str] = set()
    for methods in schema["paths"].values():
        for operation in methods.values():
            for requirement in operation.get("security", []):
                for granted in requirement.values():
                    scopes.update(granted)
    return scopes


def unrequired(permissions: Iterable[str], scopes: set[str]) -> list[str]:
    return sorted(p for p in permissions if p not in scopes)


def unreferenced(names: Iterable[str], sources: Iterable[str]) -> list[str]:
    text = "\n".join(sources)
    return sorted(n for n in names if not re.search(rf"\bErrorCode\.{n}\b", text))


def _sources() -> list[str]:
    return [
        path.read_text(encoding="utf-8")
        for package in SOURCE_PACKAGES
        for path in (ROOT / package).rglob("*.py")
    ]


def test_every_permission_is_granted_to_some_role() -> None:
    granted = set().union(*DEFAULT_ROLE_GRANTS.values())
    assert sorted(set(Permission) - granted) == []


def test_every_permission_is_required_by_some_route() -> None:
    schema = create_app(BackendSettings.model_validate(UNIT_SETTINGS)).openapi()
    assert unrequired((p.value for p in Permission), required_scopes(schema)) == []


def test_every_error_code_is_referenced() -> None:
    assert unreferenced((code.name for code in ErrorCode), _sources()) == []


def test_unrequired_fires_on_a_permission_no_route_needs() -> None:
    assert unrequired(["users:read", "ghost:write"], {"users:read"}) == ["ghost:write"]


def test_unreferenced_fires_on_a_dead_error_code() -> None:
    sources = ["raise X(code=ErrorCode.USED_ONE)"]
    assert unreferenced(["USED_ONE", "DEAD_ONE"], sources) == ["DEAD_ONE"]

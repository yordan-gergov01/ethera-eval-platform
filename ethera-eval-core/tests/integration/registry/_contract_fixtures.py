"""Contract §6 accessor: the implementer's registry helpers, failing explicitly while absent.

Role: the only door from the sealed registry oracle to the helpers of
  specs/001-product-registry/contract.md §6 (`platform_app`, `arrange_client`,
  `arrange_membership`, `arrange_product`, `product_entity_id`, `read_audit_rows`,
  `demo_document`), which the implementer writes later in tests/integration/registry_fixtures.py.
  It also holds the stand-in client the registry conftest.py hands out while the
  `started_platform_app` fixture does not exist yet.
Used by: every test module in tests/integration/registry/ (through _registry_oracle.py) and
  tests/integration/registry/conftest.py.
Depends on: `tests.integration.registry_fixtures` (unsealed, loaded lazily by name), pytest.
Key invariants: a missing helper fails the TEST that calls it (`pytest.fail` at call time, inside
  the test body), never collection and never fixture setup; the failure names the helper and the
  type of the import error, so a broken implementer module is not mistaken for an absent one;
  nothing from `backend.*`, `evals.*`, `runner.*` or `demo_target.*` is imported here.
"""

import importlib
from contextlib import AbstractAsyncContextManager
from typing import Any, NoReturn

import pytest
from httpx import AsyncClient

PROVIDER_MODULE = "tests.integration.registry_fixtures"
MISSING = "contract §6 fixture not yet provided"


def _missing(name: str, reason: str) -> NoReturn:
    pytest.fail(f"{MISSING}: {name} ({reason})", pytrace=False)


def load_provider() -> tuple[Any, str]:  # Any: the implementer's module, typed by them
    """The provider module, or None with the reason it could not be imported."""
    try:
        return importlib.import_module(PROVIDER_MODULE), ""
    except ImportError as exc:
        return None, f"{type(exc).__name__}: {exc}"


def contract_helper(name: str) -> Any:  # Any: the helper's signature is fixed by contract §6
    """The named §6 helper; fails the calling test explicitly when it is absent."""
    module, reason = load_provider()
    if module is None:
        _missing(name, reason)
    helper = getattr(module, name, None)
    if helper is None:
        _missing(name, f"{PROVIDER_MODULE} has no attribute {name!r}")
    return helper


class MissingPlatformClient:
    """Stands in for `started_platform_app` while it is absent: any use fails the test."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def __getattr__(self, name: str) -> NoReturn:
        _missing("started_platform_app", self._reason)


def platform_app(settings: Any) -> AbstractAsyncContextManager[AsyncClient]:  # Any: see above
    """§6 `platform_app(settings)`: the full platform app, entered and exited by the caller."""
    factory = contract_helper("platform_app")
    context: AbstractAsyncContextManager[AsyncClient] = factory(settings)
    return context


async def arrange_client(settings: Any, client_id: str) -> None:  # Any: opaque settings
    await contract_helper("arrange_client")(settings, client_id)


async def arrange_membership(settings: Any, username: str, client_id: str) -> None:  # Any: idem
    await contract_helper("arrange_membership")(settings, username, client_id)


async def arrange_product(
    settings: Any,  # Any: opaque settings
    client_id: str,
    project_id: str,
    document: str,
    actor_username: str,
) -> None:
    await contract_helper("arrange_product")(
        settings, client_id, project_id, document, actor_username
    )


async def product_entity_id(settings: Any, client_id: str, project_id: str) -> str:  # Any: idem
    entity_id = await contract_helper("product_entity_id")(settings, client_id, project_id)
    return str(entity_id)


async def read_audit_rows(settings: Any) -> list[Any]:  # Any: AuditRowView, implementer-typed
    rows = await contract_helper("read_audit_rows")(settings)
    return list(rows)


def demo_document(
    client_id: str = "acme", project_id: str = "support-bot", model: str = "mock-gen-small-v1"
) -> str:
    text: str = contract_helper("demo_document")(client_id, project_id, model)
    return text

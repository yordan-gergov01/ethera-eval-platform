"""Contract §6 accessor: the implementer's evaluation helpers, failing explicitly while absent.

Role: the only door from the sealed evaluation oracle to the helpers of
  specs/002-demo-target-and-dataset/contract.md §6 (`arrange_dataset_version`,
  `demo_target_client`, `demo_target_logs`), which the implementer writes later in
  tests/integration/evaluation_fixtures.py. The slice 001 helpers are reached through their own
  door, tests/integration/registry/_contract_fixtures.py.
Used by: every test module in tests/integration/evaluation/ (directly or through
  _evaluation_oracle.py).
Depends on: `tests.integration.evaluation_fixtures` (unsealed, loaded lazily by name), pytest.
Key invariants: a missing helper fails the TEST that calls it (`pytest.fail` at call time, inside
  the test body), never collection and never fixture setup; the failure names the helper and the
  type of the import error, so a broken implementer module is not mistaken for an absent one;
  `pytest.fail` raises an `OutcomeException`, not an `Exception`, so an absent helper is never
  swallowed by a `pytest.raises(Exception)` around a refused configuration; nothing from
  `backend.*`, `evals.*`, `runner.*`, `demo_target.*` or `common_lib.*` is imported here.
"""

import importlib
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, NoReturn

import pytest
from httpx import AsyncClient

PROVIDER_MODULE = "tests.integration.evaluation_fixtures"
MISSING = "contract §6 fixture not yet provided"

DemoTarget = AbstractAsyncContextManager[AsyncClient]
DemoTargetWithLogs = AbstractAsyncContextManager[tuple[AsyncClient, Callable[[], str]]]


def _missing(name: str, reason: str) -> NoReturn:
    pytest.fail(f"{MISSING}: {name} ({reason})", pytrace=False)


def _load_provider() -> tuple[Any, str]:  # Any: the implementer's module, typed by them
    try:
        return importlib.import_module(PROVIDER_MODULE), ""
    except ImportError as exc:
        return None, f"{type(exc).__name__}: {exc}"


def contract_helper(name: str) -> Any:  # Any: the helper's signature is fixed by contract §6
    """The named §6 helper; fails the calling test explicitly when it is absent."""
    module, reason = _load_provider()
    if module is None:
        _missing(name, reason)
    helper = getattr(module, name, None)
    if helper is None:
        _missing(name, f"{PROVIDER_MODULE} has no attribute {name!r}")
    return helper


async def arrange_dataset_version(
    settings: Any,  # Any: the test's `backend_settings`, opaque to the oracle
    client_id: str,
    project_id: str,
    goldens: list[dict[str, object]],
) -> int:
    """§6: publishes the next version of the Product's Dataset; returns its number."""
    number = await contract_helper("arrange_dataset_version")(
        settings, client_id, project_id, goldens
    )
    assert type(number) is int, number
    return number


def demo_target_factory() -> Callable[[str, str, str], DemoTarget]:
    """§6 `demo_target_client`, resolved now (so its absence fails before any `raises`)."""
    factory: Callable[[str, str, str], DemoTarget] = contract_helper("demo_target_client")
    return factory


def demo_target_client(model: str, instruction_set: str, retrieval: str) -> DemoTarget:
    """§6: the demo target started in-process with one configuration."""
    return demo_target_factory()(model, instruction_set, retrieval)


def demo_target_logs(model: str, instruction_set: str, retrieval: str) -> DemoTargetWithLogs:
    """§6: as `demo_target_client`, plus a function returning everything logged so far."""
    factory: Callable[[str, str, str], DemoTargetWithLogs] = contract_helper("demo_target_logs")
    return factory(model, instruction_set, retrieval)

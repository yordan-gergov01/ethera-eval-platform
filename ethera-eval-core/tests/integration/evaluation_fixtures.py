"""The evaluation module's test helpers, with exactly the signatures of contract §6 (slice 002).

Role: `arrange_dataset_version(settings, client_id, project_id, goldens)` — publishes the next
  version of a Product's Dataset (creating the Dataset at version 1 if it has none) through
  `evals.evaluation.publish_dataset_version`, which follows the seed's steps
  (`tenant_transaction` → `get_visible_product` → `publish_on`); the seed itself calls
  `publish_on` directly.
  `demo_target_client(model, instruction_set, retrieval)` — the demo target started in process
  with that configuration, reached through `httpx.ASGITransport`; `demo_target_logs(...)` — the
  same, plus a function returning everything the demo target's own logger wrote so far.
Used by: the sealed oracle in tests/integration/evaluation/ (through its `_contract_fixtures.py`
  door) and the evaluation module's own tests in tests/integration/evals/evaluation/.
Depends on: `evals.evaluation` (barrel), `evals.evaluation.domain` (`Golden`), the registry's
  helpers in tests/integration/registry_fixtures.py (`_orm`: the live app's ORM, or a
  short-lived one of the runtime role); `demo_target` (barrel), httpx.
Key invariants: writes go through `tenant_transaction([client_id])` inside the service, as the
  runtime role whenever the helper opens its own ORM, so row security applies to the fixture
  too; each Golden is validated by the domain exactly as the seed's are (PP-202, PP-205); no
  audit row is written (C-213). An unknown demo-target configuration value raises
  `UnknownConfigurationError` on entering, before any client exists (C-211); the log capture
  handler is attached for the context only and removed afterwards, so captures never leak into
  each other.
"""

import io
import logging
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from typing import cast

import httpx

from backend import BackendSettings
from demo_target import LOGGER_NAME, Configuration, create_app
from evals.evaluation import publish_dataset_version
from evals.evaluation.domain import Golden
from tests.integration.registry_fixtures import _orm


def _golden(fields: dict[str, object]) -> Golden:
    """A Golden from the §2.2 fields (without `position`), as plain JSON-like values."""
    context = fields.get("context")
    owner = fields.get("owner")
    return Golden.of(
        input=str(fields["input"]),
        expected_decision=str(fields["expected_decision"]),
        rule=str(fields["rule"]),
        failure_type=str(fields["failure_type"]),
        context=None if context is None else str(context),
        expected_numbers=cast(Iterable[str], fields.get("expected_numbers", ())),
        owner=None if owner is None else str(owner),
        unfixable_by_code=bool(fields.get("unfixable_by_code", False)),
    )


async def arrange_dataset_version(
    settings: BackendSettings,
    client_id: str,
    project_id: str,
    goldens: list[dict[str, object]],
) -> int:
    """Publish the next version of the Product's Dataset with `goldens`; its number."""
    checked = [_golden(fields) for fields in goldens]
    async with _orm(settings):
        return await publish_dataset_version(client_id, project_id, checked)


@asynccontextmanager
async def demo_target_client(
    model: str, instruction_set: str, retrieval: str
) -> AsyncIterator[httpx.AsyncClient]:
    """The demo target started in process with one configuration (contract §6)."""
    app = create_app(Configuration.of(model, instruction_set, retrieval))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://demo-target") as client:
        yield client


@asynccontextmanager
async def demo_target_logs(
    model: str, instruction_set: str, retrieval: str
) -> AsyncIterator[tuple[httpx.AsyncClient, Callable[[], str]]]:
    """As `demo_target_client`, plus everything the demo target has logged so far (§6)."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    try:
        async with demo_target_client(model, instruction_set, retrieval) as client:
            yield client, stream.getvalue
    finally:
        logger.removeHandler(handler)

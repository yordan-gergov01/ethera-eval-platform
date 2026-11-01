"""The registry's startup seed: the demo Client, its administrator's membership, the demo Product.

Role: `seed_demo_product` (the module's `ModuleMount.seed`) and `demo_document`, the demo
  Manifest text of contract §3.1, re-targetable for tests.
Used by: `evals.registry.module` (the mount); `evals.registry` barrel, and through it
  tests/integration/registry_fixtures.py.
Depends on: the `backend` barrel (`SeedContext`, `ensure_client`, `ensure_membership`),
  `evals.registry.services.manifests.create_product`.
Key invariants: create-only — runs at every start, creates whatever is missing of Client
  `acme`, the seeded administrator's Membership and Product `acme / support-bot` at version 1
  with its `manifest_created` audit row (actor: the seeded administrator, no client address),
  and never touches what exists, even a Product replaced since (contract §3.1). Startups are
  serialised by the core's startup lock, so concurrent instances seed once.
"""

from backend import SeedContext, ensure_client, ensure_membership
from evals.registry.services.manifests import create_product

DEMO_CLIENT_ID = "acme"
DEMO_PROJECT_ID = "support-bot"
DEMO_MODEL = "mock-gen-small-v1"
DEMO_TEMPLATE = """product:
  client_id: {client_id}
  project_id: {project_id}
bindings:
  - role: generation
    provider: mock
    model: {model}
allowed_providers:
  - mock
"""


def demo_document(
    client_id: str = DEMO_CLIENT_ID, project_id: str = DEMO_PROJECT_ID, model: str = DEMO_MODEL
) -> str:
    """The demo Manifest of contract §3.1, for the given Product and generation model."""
    return DEMO_TEMPLATE.format(client_id=client_id, project_id=project_id, model=model)


async def seed_demo_product(context: SeedContext) -> None:
    """Create whatever is missing of the demo Client, Membership and Product."""
    await ensure_client(DEMO_CLIENT_ID)
    await ensure_membership(context.admin_user_id, DEMO_CLIENT_ID)
    await create_product(
        DEMO_CLIENT_ID,
        DEMO_PROJECT_ID,
        demo_document(),
        context.admin_user_id,
        context.admin_username,
    )

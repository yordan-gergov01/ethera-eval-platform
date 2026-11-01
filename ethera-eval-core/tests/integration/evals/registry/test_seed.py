"""The registry seed under concurrent startups: one of everything, whoever starts first.

Role: pins evals.registry.services.seed `seed_demo_product` as two platform instances run it at
  the same time on one database (contract §3.1): the core's startup lock serialises the two
  `prepare_database` runs, so exactly one Client, one Membership, one Product, one version and
  one audit row exist afterwards.
Used by: pytest (integration; needs the test database).
Depends on: `backend_settings`, `connect_as_owner` from tests/integration/conftest.py;
  backend.core.startup `prepare_database`, the core admin seed, `evals.MODULES`.
Key invariants: two startup-lock holders in two tasks stand in for two processes (one test
  process cannot hold two live apps; contract §1); the counts are read as the owner, past row
  security.
"""

import asyncio

from backend import BackendSettings
from backend.core.security import Argon2PasswordHasher
from backend.core.startup import prepare_database
from backend.services.seeding import AdminAccount, build_seeding_service
from evals.MODULES import MODULES
from tests.integration.conftest import connect_as_owner


async def _start(settings: BackendSettings) -> None:
    account = AdminAccount(
        username=settings.admin_username,
        email=settings.admin_email,
        password=settings.admin_password,
    )
    await prepare_database(
        settings,
        MODULES,
        seed_core=lambda: build_seeding_service(Argon2PasswordHasher()).seed(account),
        admin_username=settings.admin_username,
    )


async def test_concurrent_startups_seed_the_demo_product_once(
    backend_settings: BackendSettings,
) -> None:
    await asyncio.gather(_start(backend_settings), _start(backend_settings))

    connection = await connect_as_owner(backend_settings)
    try:
        counts = {
            table: await connection.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed names
            for table in (
                "clients",
                "client_memberships",
                "reg_products",
                "reg_manifests",
                "audit_rows",
            )
        }
    finally:
        await connection.close()

    assert counts == {
        "clients": 1,
        "client_memberships": 1,
        "reg_products": 1,
        "reg_manifests": 1,
        "audit_rows": 1,
    }

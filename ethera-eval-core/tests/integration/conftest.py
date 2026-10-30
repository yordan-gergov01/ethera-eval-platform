"""Integration fixtures: a fresh database per test, the real app, and the test broker.

Role: connects the integration tests to the real PostgreSQL and RabbitMQ of the test stack.
  Start both with:

      docker compose -f docker-compose.test.yml -p ethera_eval_core_test up -d --wait \\
          postgres rabbitmq

Used by: every test module in tests/integration/ (fixtures `fresh_database`, `backend_settings`,
  `started_app`, `broker_available`, `empty_queues`; helpers such as `broker_channel`,
  `create_user`, `connect_as_app`, `token_for`, `assert_problem`, `eventually`).
Depends on: the test PostgreSQL (with pgvector) and RabbitMQ (users backend, runner, inspector)
  of docker-compose.test.yml; `backend.main.create_app`; `common_lib.messaging.declare`.
Key invariants: unreachable services skip the tests locally but fail them with
  REQUIRE_INTEGRATION=1 (set in the Docker test runner), so nothing passes silently; each test
  that takes `fresh_database` gets its own database, its extension created by the superuser
  and everything else by the non-superuser app role, dropped afterwards; all credentials are
  fixed, fake test values.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import aio_pika
import asyncpg
import pytest
from aio_pika.abc import AbstractChannel
from aio_pika.exceptions import AMQPConnectionError
from httpx import ASGITransport, AsyncClient, Response
from pydantic import SecretStr

from backend.core.security import Argon2PasswordHasher
from backend.core.settings import BackendSettings, DatabaseSettings
from backend.main import create_app
from common_lib.messaging.declare import declare_topology
from common_lib.messaging.topology import JOBS_QUEUE, RESULTS_QUEUE
from common_lib.settings import BrokerSettings

START_COMMAND = (
    "docker compose -f docker-compose.test.yml -p ethera_eval_core_test "
    "up -d --wait postgres rabbitmq"
)


@dataclass(frozen=True)
class TestDatabaseServer:
    """Connection details of the test PostgreSQL; the values are fixed and fake."""

    host: str = os.environ.get("TEST_DB_HOST", "127.0.0.1")
    port: int = int(os.environ.get("TEST_DB_PORT", "55432"))
    maintenance_db: str = os.environ.get("TEST_DB_NAME", "ethera_eval_test")
    superuser: str = os.environ.get("TEST_DB_SUPERUSER", "postgres")
    superuser_password: str = os.environ.get("TEST_DB_SUPERUSER_PASSWORD", "test-only-not-a-secret")
    app_user: str = os.environ.get("TEST_DB_APP_USER", "ethera_eval_app")
    app_password: str = os.environ.get("TEST_DB_APP_PASSWORD", "test-only-not-a-secret")

    async def connect_as_superuser(self, database: str) -> asyncpg.Connection:
        return await asyncpg.connect(
            host=self.host,
            port=self.port,
            user=self.superuser,
            password=self.superuser_password,
            database=database,
            timeout=3,
        )


SERVER = TestDatabaseServer()


@dataclass(frozen=True)
class TestBroker:
    """Connection details of the test RabbitMQ; the values are fixed and fake."""

    host: str = os.environ.get("TEST_BROKER_HOST", "127.0.0.1")
    port: int = int(os.environ.get("TEST_BROKER_PORT", "55672"))
    vhost: str = "ethera_eval_test"
    password: str = "test-only-not-a-secret"

    def settings_for(self, user: str) -> BrokerSettings:
        """Settings of one of the provisioned users: backend, runner or inspector."""
        return BrokerSettings(
            rabbitmq_host=self.host,
            rabbitmq_port=self.port,
            rabbitmq_vhost=self.vhost,
            rabbitmq_user=user,
            rabbitmq_password=SecretStr(self.password),
        )


BROKER = TestBroker()


@asynccontextmanager
async def broker_channel(user: str) -> AsyncIterator[AbstractChannel]:
    """A channel on the test broker as one of the provisioned users."""
    connection = await aio_pika.connect(
        host=BROKER.host,
        port=BROKER.port,
        login=user,
        password=BROKER.password,
        virtualhost=BROKER.vhost,
        timeout=5,
    )
    async with connection, connection.channel() as channel:
        yield channel


@pytest.fixture
async def empty_queues(broker_available: None) -> None:
    """The full topology, declared and emptied; each queue is purged by a user allowed to."""
    async with broker_channel("backend") as channel:
        await declare_topology(channel, (JOBS_QUEUE, RESULTS_QUEUE))
    purgers = {
        JOBS_QUEUE.name: "runner",
        RESULTS_QUEUE.name: "backend",
        JOBS_QUEUE.dead_letter_queue: "backend",
        RESULTS_QUEUE.dead_letter_queue: "inspector",
    }
    for queue, user in purgers.items():
        async with broker_channel(user) as channel:
            await (await channel.get_queue(queue, ensure=False)).purge()


@pytest.fixture(scope="session", autouse=True)
def _require_test_database() -> None:
    async def probe() -> None:
        connection = await SERVER.connect_as_superuser(SERVER.maintenance_db)
        await connection.close()

    try:
        asyncio.run(probe())
    except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
        message = (
            f"test PostgreSQL not reachable on {SERVER.host}:{SERVER.port} "
            f"({type(exc).__name__}); start it with: {START_COMMAND}"
        )
        _skip_or_fail(message)


def _skip_or_fail(message: str) -> None:
    if os.environ.get("REQUIRE_INTEGRATION") == "1":
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


@pytest.fixture(scope="session")
def broker_available() -> None:
    """Tests that need the test RabbitMQ use this; others run without it."""

    async def probe() -> None:
        connection = await aio_pika.connect(
            host=BROKER.host,
            port=BROKER.port,
            login="backend",
            password=BROKER.password,
            virtualhost=BROKER.vhost,
            timeout=3,
        )
        await connection.close()

    try:
        asyncio.run(probe())
    except (OSError, AMQPConnectionError, TimeoutError) as exc:
        _skip_or_fail(
            f"test RabbitMQ not reachable on {BROKER.host}:{BROKER.port} "
            f"({type(exc).__name__}); start it with: {START_COMMAND}"
        )


@pytest.fixture
async def fresh_database() -> AsyncIterator[DatabaseSettings]:
    """A new, empty database owned by the application role, dropped afterwards.

    Mirrors production: the extension is created by the superuser, everything else
    by the non-superuser application role.
    """
    name = f"it_{uuid4().hex[:12]}"
    admin = await SERVER.connect_as_superuser(SERVER.maintenance_db)
    try:
        await admin.execute(f'CREATE DATABASE "{name}" OWNER "{SERVER.app_user}"')
        database = await SERVER.connect_as_superuser(name)
        try:
            await database.execute("CREATE EXTENSION IF NOT EXISTS vector")
        finally:
            await database.close()

        yield DatabaseSettings(
            db_host=SERVER.host,
            db_port=SERVER.port,
            db_name=name,
            db_user=SERVER.app_user,
            db_password=SecretStr(SERVER.app_password),
        )
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()


ADMIN_PASSWORD = "test-only-admin-password"


@pytest.fixture
def backend_settings(fresh_database: DatabaseSettings) -> BackendSettings:
    """Complete backend settings for the fresh database, with fake secrets."""
    return BackendSettings.model_validate(
        fresh_database.model_dump()
        | {
            "jwt_secret": "test-only-not-a-secret-signing-key-32-bytes-long",
            "admin_username": "admin",
            "admin_email": "admin@example.com",
            "admin_password": ADMIN_PASSWORD,
        }
        | BROKER.settings_for("backend").model_dump()
    )


@pytest.fixture
async def started_app(backend_settings: BackendSettings) -> AsyncIterator[AsyncClient]:
    """The real application after its full startup: migrations, pool and seeding."""
    app = create_app(backend_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def create_user(
    settings: DatabaseSettings,
    *,
    username: str,
    password: str,
    role: str = "user",
    is_active: bool = True,
) -> None:
    """Insert a user directly, for tests that need more than the seeded admin."""
    password_hash = await Argon2PasswordHasher().hash(password)
    connection = await connect_as_app(settings)
    try:
        await connection.execute(
            "INSERT INTO users (id, username, email, full_name, password_hash, is_active, "
            "token_version, role_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), $1::text, $1::text || '@example.com', $1::text, $2, $3, 0, "
            "r.id, now(), now() "
            "FROM roles r WHERE r.name = $4",
            username,
            password_hash,
            is_active,
            role,
        )
    finally:
        await connection.close()


async def connect_as_app(settings: DatabaseSettings) -> asyncpg.Connection:
    """A direct connection as the application role, for assertions on stored data."""
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        database=settings.db_name,
    )


async def login(client: AsyncClient, username: str, password: str) -> Response:
    return await client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )


async def token_for(client: AsyncClient, username: str, password: str) -> str:
    response = await login(client, username, password)
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_problem(response: Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


async def eventually(check: Callable[[], Awaitable[bool]], *, seconds: float = 15) -> None:
    """Wait until `check` holds, for work the backend does in the background."""
    for _ in range(int(seconds * 10)):
        if await check():
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"condition not met within {seconds} seconds")

"""The backend connects to RabbitMQ in the background and never needs it to start.

Role: pins the broker lifecycle of the backend app (`app.state.broker`, a
  backend.messaging.connection `BrokerConnection`): it connects with its own user, and starts
  and serves /health while the broker is down.
Used by: pytest (integration — needs the test database; the first test also the broker).
Depends on: `backend_settings` and `broker_available` from tests/integration/conftest.py.
Key invariants: the "down" broker is a port nothing listens on; shutting down while it is down
  leaves no task running, since a leftover reconnect task would keep the process alive.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.settings import BackendSettings
from backend.main import create_app


@pytest.mark.usefixtures("broker_available")
async def test_backend_connects_to_the_broker_with_its_own_user(
    backend_settings: BackendSettings,
) -> None:
    app = create_app(backend_settings)

    async with app.router.lifespan_context(app):
        async with asyncio.timeout(15):
            connection = await app.state.broker.wait_until_connected()
        assert not connection.is_closed

    assert connection.is_closed


async def test_backend_starts_and_serves_without_the_broker(
    backend_settings: BackendSettings,
) -> None:
    # Nothing listens on this port: the broker is "down".
    app = create_app(backend_settings.model_copy(update={"rabbitmq_port": 1}))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        health = await client.get("/health")
        assert app.state.broker.connection is None

    assert health.status_code == 200
    # Shutting down while the broker is down leaves nothing running: a leftover reconnect
    # task would keep the process from exiting.
    assert [t for t in asyncio.all_tasks() if t is not asyncio.current_task()] == []

"""The real application, after its full startup, reports healthy against PostgreSQL.

Role: pins the /health contract of the backend (backend/api/health.py) on the real stack:
  status and database both "ok".
Used by: pytest (integration — needs the test database).
Depends on: `started_app` from tests/integration/conftest.py.
Key invariants: drives the real ASGI app after migrations, pool and seeding; nothing mocked.
"""

from httpx import AsyncClient


async def test_started_application_reports_healthy(started_app: AsyncClient) -> None:
    response = await started_app.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}

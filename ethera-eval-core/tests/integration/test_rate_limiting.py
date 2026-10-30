"""Rate limiting end to end, with the counters in the real PostgreSQL.

Role: pins the HTTP rate-limit contract (backend.api.dependencies.rate_limit over
  backend/services/rate_limit): 429 problem details with X-RateLimit-* and Retry-After headers,
  a quota per user or per address, the stricter login rule keyed by address and username,
  unlimited /health and /docs, trusted-proxy client addresses, 429 in OpenAPI.
Used by: pytest (integration — needs the test database).
Depends on: `backend_settings`, `started_app`, `create_user`, `login`, `token_for`, `bearer`,
  `assert_problem`, `ADMIN_PASSWORD` from tests/integration/conftest.py.
Key invariants: drives the real ASGI app with small limits set through settings, never mocks
  our own code; two app instances on one database share the counters like replicas; the rate
  headers are exposed to the browser through CORS.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from httpx import ASGITransport, AsyncClient, Response

from backend.core.settings import BackendSettings
from backend.main import create_app
from tests.integration.conftest import (
    ADMIN_PASSWORD,
    assert_problem,
    bearer,
    create_user,
    login,
    token_for,
)

ME = "/api/v1/users/me"
FRONTEND = "http://localhost:3000"
PASSWORD = "test-only-plain-user-password"


@asynccontextmanager
async def running_app(settings: BackendSettings, **limits: Any) -> AsyncIterator[AsyncClient]:
    """The real application with its full startup, using the given limits."""
    app = create_app(settings.model_copy(update=limits))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


def limit_headers(response: Response) -> tuple[str, str, str]:
    return (
        response.headers["x-ratelimit-limit"],
        response.headers["x-ratelimit-remaining"],
        response.headers["x-ratelimit-reset"],
    )


async def test_requests_over_the_limit_get_429_with_headers(
    backend_settings: BackendSettings,
) -> None:
    async with running_app(backend_settings, rate_limit_default_requests=3) as client:
        responses = [await client.get(ME, headers={"Origin": FRONTEND}) for _ in range(4)]

    # Error responses after the check carry the headers too.
    assert [r.status_code for r in responses] == [401, 401, 401, 429]
    assert [limit_headers(r)[:2] for r in responses[:3]] == [("3", "2"), ("3", "1"), ("3", "0")]
    # Accepted responses report the end of the current window; the 429 reports Retry-After,
    # which may be longer than a window (checked below).
    assert all(1 <= int(limit_headers(r)[2]) <= 60 for r in responses[:3])

    rejected = responses[3]
    assert_problem(rejected, 429, "RATE_LIMITED")
    retry_after = rejected.headers["retry-after"]
    assert limit_headers(rejected) == ("3", "0", retry_after)
    assert 1 <= int(retry_after) <= 120
    exposed = rejected.headers["access-control-expose-headers"].lower()
    assert {"retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"} <= {
        h.strip() for h in exposed.split(",")
    }


async def test_each_user_has_an_own_quota(backend_settings: BackendSettings) -> None:
    async with running_app(backend_settings, rate_limit_default_requests=4) as client:
        await create_user(backend_settings, username="dora", password=PASSWORD)
        # Two logins: the anonymous (address) quota now has 2 left.
        admin = await token_for(client, "admin", ADMIN_PASSWORD)
        dora = await token_for(client, "dora", PASSWORD)

        admin_calls = [await client.get(ME, headers=bearer(admin)) for _ in range(5)]
        dora_call = await client.get(ME, headers=bearer(dora))
        anonymous_call = await client.get(ME)

    assert [r.status_code for r in admin_calls] == [200, 200, 200, 200, 429]
    assert dora_call.status_code == 200
    assert limit_headers(dora_call)[1] == "3"
    assert anonymous_call.status_code == 401
    assert limit_headers(anonymous_call)[1] == "1"


async def test_invalid_token_counts_against_the_address(backend_settings: BackendSettings) -> None:
    async with running_app(backend_settings, rate_limit_default_requests=2) as client:
        await client.get(ME, headers=bearer("not-a-valid-token"))
        await client.get(ME)
        rejected = await client.get(ME, headers=bearer("another-invalid-token"))

    assert_problem(rejected, 429, "RATE_LIMITED")


async def test_sixth_login_attempt_is_429_even_with_the_right_password(
    backend_settings: BackendSettings,
) -> None:
    async with running_app(backend_settings) as client:
        await create_user(backend_settings, username="dora", password=PASSWORD)
        wrong = [await login(client, "admin", "not-the-password-at-all") for _ in range(5)]
        sixth = await login(client, "Admin", ADMIN_PASSWORD)
        other_user = await login(client, "dora", PASSWORD)

    assert [r.status_code for r in wrong] == [401] * 5
    # The headers describe the stricter login rule, not the default one.
    assert [limit_headers(r)[:2] for r in wrong] == [("5", str(4 - i)) for i in range(5)]
    assert_problem(sixth, 429, "RATE_LIMITED")
    assert sixth.headers["x-ratelimit-limit"] == "5"
    # The key is address + username: the attacker does not lock out other accounts.
    assert other_user.status_code == 200


async def test_health_and_docs_are_never_limited(backend_settings: BackendSettings) -> None:
    async with running_app(backend_settings, rate_limit_default_requests=1) as client:
        responses = [await client.get(path) for path in ["/health", "/docs"] * 5]

    assert {r.status_code for r in responses} == {200}
    assert not any("x-ratelimit-limit" in r.headers for r in responses)


async def test_replicas_share_the_counters(backend_settings: BackendSettings) -> None:
    async with (
        running_app(backend_settings, rate_limit_default_requests=3) as first,
        running_app(backend_settings, rate_limit_default_requests=3) as second,
    ):
        statuses = [(await client.get(ME)).status_code for client in (first, second, first, second)]

    assert statuses == [401, 401, 401, 429]


async def test_clients_behind_a_trusted_proxy_are_told_apart(
    backend_settings: BackendSettings,
) -> None:
    # The test transport connects from 127.0.0.1, which plays the trusted proxy.
    async with running_app(
        backend_settings, rate_limit_default_requests=1, trusted_proxies=("127.0.0.1",)
    ) as client:
        first = await client.get(ME, headers={"X-Forwarded-For": "203.0.113.1"})
        second = await client.get(ME, headers={"X-Forwarded-For": "203.0.113.2"})
        repeated = await client.get(ME, headers={"X-Forwarded-For": "203.0.113.1"})

    assert (first.status_code, second.status_code) == (401, 401)
    assert_problem(repeated, 429, "RATE_LIMITED")


async def test_openapi_documents_429(started_app: AsyncClient) -> None:
    schema = (await started_app.get("/openapi.json")).json()

    assert "429" in schema["paths"]["/api/v1/users/me"]["get"]["responses"]
    assert "429" in schema["paths"]["/api/v1/auth/login"]["post"]["responses"]


async def test_cleanup_task_runs_while_the_app_runs(started_app: AsyncClient) -> None:
    names = {task.get_name() for task in asyncio.all_tasks()}

    assert "rate_limit_cleanup" in names

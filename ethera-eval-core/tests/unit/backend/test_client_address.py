"""Client address: X-Forwarded-For counts only when a trusted proxy sends it.

Role: pins `trusted_proxies` in backend.core.settings `BackendSettings` (empty by default, a
  comma-separated list of addresses or networks, wildcards and host names rejected) and how
  `backend.main.create_app` applies it to the client address.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py; a
  `/whoami` route added to the app; httpx `ASGITransport` with a chosen client address.
Key invariants: without trusted proxies, or from an untrusted sender, X-Forwarded-For is
  ignored, so a client cannot spoof its address (which keys the rate limits).
"""

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.core.settings import BackendSettings
from backend.main import create_app

PROXY = "172.18.0.5"
FORWARDED = {"X-Forwarded-For": "203.0.113.7"}


def build_app(trusted_proxies: str = "") -> FastAPI:
    app = create_app(BackendSettings.model_validate({"trusted_proxies": trusted_proxies}))

    @app.get("/whoami")
    async def whoami(request: Request) -> str:
        assert request.client is not None
        return request.client.host

    return app


async def client_seen(app: FastAPI, *, connecting_from: str, headers: dict[str, str]) -> str:
    transport = ASGITransport(app=app, client=(connecting_from, 51234))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/whoami", headers=headers)
    host: str = response.json()
    return host


def test_no_proxy_is_trusted_by_default() -> None:
    assert BackendSettings().trusted_proxies == ()


def test_proxies_are_read_as_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", "172.18.0.0/16, 10.0.0.1")

    assert BackendSettings().trusted_proxies == ("172.18.0.0/16", "10.0.0.1")


@pytest.mark.parametrize("proxies", ["*", "proxy.internal", "10.0.0.0/33"])
def test_wildcards_and_host_names_are_rejected(
    monkeypatch: pytest.MonkeyPatch, proxies: str
) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", proxies)

    with pytest.raises(ValidationError, match="trusted_proxies"):
        BackendSettings()


async def test_forwarded_header_is_ignored_without_trusted_proxies() -> None:
    seen = await client_seen(build_app(), connecting_from=PROXY, headers=FORWARDED)

    assert seen == PROXY


async def test_forwarded_header_from_a_trusted_proxy_names_the_client() -> None:
    seen = await client_seen(build_app("172.18.0.0/16"), connecting_from=PROXY, headers=FORWARDED)

    assert seen == "203.0.113.7"


async def test_forwarded_header_from_an_untrusted_sender_is_ignored() -> None:
    seen = await client_seen(
        build_app("172.18.0.0/16"), connecting_from="198.51.100.9", headers=FORWARDED
    )

    assert seen == "198.51.100.9"

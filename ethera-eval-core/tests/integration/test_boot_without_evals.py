"""The platform core boots and serves with the domain package absent.

Role: the CI proof of the Bible's "core must boot with any domain module absent" — the
  boundary that also separates core and domain ownership (docs/DECISIONS.md D-003).
Used by: pytest (integration; needs the test database and broker).
Depends on: a fresh database and broker from tests/integration/conftest.py; a subprocess so
  that no module imported by other tests can mask an import of `evals`.
Key invariants: in the subprocess `sys.modules["evals"] = None`, so ANY import of `evals`
  (direct or indirect) raises ImportError; the core app must still run its full lifespan
  (migrations, seeding) and answer `/health` 200. The negative test proves the blocker fires.
"""

import json
import subprocess
import sys
import textwrap
from typing import Any

from pydantic import SecretStr

from backend.core.settings import BackendSettings

BOOT_CORE_ONLY = textwrap.dedent(
    """
    import asyncio, json, sys
    sys.modules["evals"] = None  # any import of the domain package now fails

    from httpx import ASGITransport, AsyncClient
    from backend.core.settings import BackendSettings
    from backend.main import create_app

    async def main() -> None:
        settings = BackendSettings.model_validate(json.loads(sys.stdin.read()))
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
        assert sys.modules.get("evals") is None  # never imported, even indirectly
        print(response.status_code)

    asyncio.run(main())
    """
)

IMPORT_DOMAIN_WHILE_BLOCKED = textwrap.dedent(
    """
    import sys
    sys.modules["evals"] = None
    import evals.app
    """
)


def _plain(settings: BackendSettings) -> dict[str, Any]:
    """The settings as JSON-safe values, secrets included (the subprocess needs them)."""
    values = settings.model_dump()
    return {
        key: value.get_secret_value() if isinstance(value, SecretStr) else value
        for key, value in values.items()
    }


def _run(code: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_core_boots_and_serves_health_without_the_domain_package(
    backend_settings: BackendSettings,
) -> None:
    result = _run(BOOT_CORE_ONLY, json.dumps(_plain(backend_settings), default=str))
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "200"


def test_blocking_the_domain_package_makes_its_import_fail() -> None:
    result = _run(IMPORT_DOMAIN_WHILE_BLOCKED)
    assert result.returncode != 0
    assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr

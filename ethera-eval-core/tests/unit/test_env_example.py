"""`.env.example`, `docker-compose.yml` and the services' settings must not drift apart.

Role: pins the configuration contract between .env.example, docker-compose.yml and the settings
  classes (backend.core.settings `BackendSettings`, runner.settings `RunnerSettings`): a fresh
  clone runs with `cp .env.example .env && docker compose up -d`.
Used by: pytest (unit).
Depends on: the files .env.example and docker-compose.yml at the ethera-eval-core root, read
  with PyYAML; no services.
Key invariants: every variable compose needs is in the example and the example carries nothing
  unused; each service container receives every setting it cannot start without and nothing
  its settings do not know; the runner receives no database settings.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from backend.core.settings import BackendSettings
from common_lib.settings import ServiceSettings
from runner.settings import RunnerSettings

ROOT = Path(__file__).resolve().parents[2]

# ${NAME}, ${NAME:-default} or ${NAME:?message}; $${NAME} is an escaped literal.
_COMPOSE_VARIABLE = re.compile(r"(?<!\$)\$\{([A-Z][A-Z0-9_]*)")


def env_example_variables() -> set[str]:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    return {
        line.split("=", 1)[0].strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }


def compose_text() -> str:
    return (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def compose_variables() -> set[str]:
    return set(_COMPOSE_VARIABLE.findall(compose_text()))


# Each service container and the settings class it loads.
SERVICES: dict[str, type[ServiceSettings]] = {"backend": BackendSettings, "runner": RunnerSettings}


def service_environment(service: str) -> set[str]:
    compose: dict[str, Any] = yaml.safe_load(compose_text())
    return set(compose["services"][service]["environment"])


def test_every_compose_variable_is_in_the_example() -> None:
    missing = compose_variables() - env_example_variables()

    assert not missing, f"add to .env.example: {sorted(missing)}"


def test_the_example_has_no_unused_variables() -> None:
    unused = env_example_variables() - compose_variables()

    assert not unused, f"not used by docker-compose.yml: {sorted(unused)}"


@pytest.mark.parametrize("service", SERVICES)
def test_each_service_receives_every_required_setting(service: str) -> None:
    settings = SERVICES[service]
    required = {
        name.upper() for name, field in settings.model_fields.items() if field.is_required()
    }

    missing = required - service_environment(service)

    assert not missing, f"pass to the {service} service in docker-compose.yml: {sorted(missing)}"


@pytest.mark.parametrize("service", SERVICES)
def test_each_service_receives_only_known_settings(service: str) -> None:
    settings = SERVICES[service]
    known = {name.upper() for name in settings.model_fields}

    unknown = service_environment(service) - known

    assert not unknown, f"no {settings.__name__} field for: {sorted(unknown)} (typo?)"


def test_the_runner_receives_no_database_settings() -> None:
    assert not {
        name for name in service_environment("runner") if name.startswith(("DB_", "POSTGRES"))
    }

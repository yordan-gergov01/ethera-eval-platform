"""Settings base shared by the backend and the runner.

Role: `ServiceSettings` (base: log level and format), `BrokerSettings` (RabbitMQ with the
  service's own user) and `load_settings`. Each service defines one settings class and creates
  it once at startup.
Used by: `backend.core.settings`, `backend.main`, `runner.settings`, `runner.main`,
  `common_lib.messaging.connection`, `evals.migration_cli`; the settings and `.env.example` tests.
Depends on: pydantic-settings, `common_lib.logging_config` (level and format types).
Key invariants: values come only from environment variables; nothing else in the code reads
  `os.environ`. Settings are immutable. A validation error never repeats the rejected value
  (`hide_input_in_errors`, and `load_settings` prints only names and reasons, then exits 1), so a
  mistyped secret cannot leak. Each service gets its own broker credentials (template_core D-002).
"""

import sys

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from common_lib.logging_config import LogFormat, LogLevel


class ServiceSettings(BaseSettings):
    """Base class for a service's settings: environment variables only, immutable."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        frozen=True,
        # Settings hold secrets: a validation error must never repeat the rejected value,
        # however it is rendered.
        hide_input_in_errors=True,
    )

    log_level: LogLevel = "INFO"
    # JSON lines in containers; "console" for readable local output.
    log_format: LogFormat = "json"


class BrokerSettings(ServiceSettings):
    """Connection to RabbitMQ, with this service's own user.

    Each service receives its own credentials as RABBITMQ_USER and RABBITMQ_PASSWORD;
    the broker grants each user only what that service needs.
    """

    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = Field(default=5672, ge=1, le=65535)
    rabbitmq_vhost: str
    rabbitmq_user: str
    rabbitmq_password: SecretStr
    # Unacknowledged messages a consumer may hold at once.
    rabbitmq_prefetch_count: int = Field(default=10, ge=1, le=1000)


def load_settings[SettingsT: ServiceSettings](settings_cls: type[SettingsT]) -> SettingsT:
    """Create the settings or stop the process with a clear, value-free message.

    A missing or invalid variable is reported by its environment variable name
    together with the reason. The offending value itself is never printed, so a
    mistyped secret cannot leak into the logs.
    """
    try:
        return settings_cls()
    except ValidationError as exc:
        print(_format_errors(exc), file=sys.stderr)  # noqa: T201 - logging is not configured yet
        raise SystemExit(1) from None


def _format_errors(exc: ValidationError) -> str:
    errors = exc.errors(include_input=False, include_url=False)
    lines = [f"Configuration error: {len(errors)} environment variable(s) missing or invalid."]
    for error in errors:
        name = ".".join(str(part) for part in error["loc"]).upper() or "<settings>"
        lines.append(f"  - {name}: {error['msg']}")
    return "\n".join(lines)

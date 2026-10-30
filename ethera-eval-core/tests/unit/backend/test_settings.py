"""Backend settings: explicit CORS origins and a strong, normalised admin account.

Role: pins backend.core.settings `BackendSettings`: CORS origins default to the local frontend
  and are read as a comma-separated list, wildcards and malformed origins are rejected, the
  admin identity is normalised, and a weak admin password stops startup via
  common_lib.settings `load_settings`.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py;
  `monkeypatch` for environment overrides. No services.
Key invariants: a rejected admin password never appears in the validation error, only the
  reason does.
"""

import pytest
from pydantic import ValidationError

from backend.core.settings import BackendSettings
from common_lib.settings import load_settings


def test_defaults_allow_the_local_frontend() -> None:
    settings = BackendSettings()

    assert settings.cors_allowed_origins == ("http://localhost:3000",)
    assert settings.enable_api_docs is True


def test_origins_are_read_as_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000, https://app.example.com")

    assert BackendSettings().cors_allowed_origins == (
        "http://localhost:3000",
        "https://app.example.com",
    )


def test_admin_identity_is_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", " Admin ")
    monkeypatch.setenv("ADMIN_EMAIL", "Admin@Example.COM")

    settings = BackendSettings()

    assert settings.admin_username == "admin"
    assert settings.admin_email == "admin@example.com"


@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("short", "at least 12"),
        ("qwerty123456", "too common"),
        ("admin@example.com", "username or email"),
    ],
)
def test_weak_admin_password_stops_startup(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    password: str,
    reason: str,
) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", password)

    with pytest.raises(SystemExit):
        load_settings(BackendSettings)

    report = capsys.readouterr().err
    assert "ADMIN_PASSWORD" in report
    assert reason in report


def test_weak_admin_password_never_appears_in_the_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A well-known common password, used to prove it is rejected and never echoed.
    monkeypatch.setenv("ADMIN_PASSWORD", "qwerty123456")  # gitleaks:allow

    with pytest.raises(ValidationError) as rejected:
        BackendSettings()

    # Even the library's own rendering of the error shows only the masked value.
    assert "qwerty123456" not in str(rejected.value)
    assert "too common" in str(rejected.value)


@pytest.mark.parametrize(
    "origins",
    ["*", "http://localhost:3000,*", "https://app.example.com/", "app.example.com", " , "],
)
def test_wildcards_and_malformed_origins_are_rejected(
    monkeypatch: pytest.MonkeyPatch, origins: str
) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)

    with pytest.raises(ValidationError, match="cors_allowed_origins"):
        BackendSettings()

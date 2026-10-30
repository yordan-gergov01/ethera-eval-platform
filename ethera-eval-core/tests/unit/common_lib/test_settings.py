"""Fail-fast settings loading: clear messages naming the variable, never the value.

Role: pins common_lib.settings `ServiceSettings` and `load_settings`: a valid environment loads,
  a missing or invalid variable exits with code 1 and names the variable on stderr, and loaded
  settings are immutable.
Used by: pytest (unit).
Depends on: a local `ExampleSettings` subclass; `monkeypatch` and `capsys`. No services.
Key invariants: a rejected value never appears on stderr or in the validation error itself, so
  a misconfigured secret cannot leak through a startup failure.
"""

import pytest
from pydantic import Field, SecretStr, ValidationError

from common_lib.settings import ServiceSettings, load_settings

SECRET_VALUE = "too-short-but-sensitive"


class ExampleSettings(ServiceSettings):
    example_secret: SecretStr = Field(min_length=32)
    example_port: int


def test_valid_environment_returns_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_SECRET", "x" * 32)
    monkeypatch.setenv("EXAMPLE_PORT", "8000")

    settings = load_settings(ExampleSettings)

    assert settings.example_port == 8000
    assert settings.example_secret.get_secret_value() == "x" * 32


def test_missing_variable_exits_and_names_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EXAMPLE_SECRET", "x" * 32)
    monkeypatch.delenv("EXAMPLE_PORT", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        load_settings(ExampleSettings)

    assert exit_info.value.code == 1
    stderr = capsys.readouterr().err
    assert "EXAMPLE_PORT" in stderr
    assert "Field required" in stderr


def test_invalid_secret_is_reported_without_its_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EXAMPLE_SECRET", SECRET_VALUE)
    monkeypatch.setenv("EXAMPLE_PORT", "not-a-number")

    with pytest.raises(SystemExit):
        load_settings(ExampleSettings)

    stderr = capsys.readouterr().err
    assert "EXAMPLE_SECRET" in stderr
    assert "EXAMPLE_PORT" in stderr
    assert SECRET_VALUE not in stderr
    assert "not-a-number" not in stderr


def test_rejected_values_never_appear_in_the_error_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_SECRET", SECRET_VALUE)
    monkeypatch.setenv("EXAMPLE_PORT", "not-a-number")

    with pytest.raises(ValidationError) as rejected:
        ExampleSettings()

    assert SECRET_VALUE not in str(rejected.value)
    assert "not-a-number" not in str(rejected.value)


def test_settings_are_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_SECRET", "x" * 32)
    monkeypatch.setenv("EXAMPLE_PORT", "8000")
    settings = load_settings(ExampleSettings)

    with pytest.raises(ValueError, match="frozen"):
        settings.example_port = 9000  # type: ignore[misc]

"""One normalisation for usernames and emails, wherever they enter the system.

Role: pins common_lib.schemas.identity `Username`, `Email` and `normalize_identifier`: case,
  whitespace and full-width variants normalise to one name, emails are lowercased entirely, and
  invalid usernames and emails are rejected.
Used by: pytest (unit).
Depends on: pydantic `TypeAdapter`; no fixtures or services.
Key invariants: login input goes through the same normalisation as stored identifiers, so a
  variant spelling can never name a different account.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from common_lib.schemas.identity import Email, Username, normalize_identifier

USERNAME = TypeAdapter(Username)
EMAIL = TypeAdapter(Email)


def full_width(text: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if c.isalnum() else c for c in text)


@pytest.mark.parametrize("raw", ["admin", "Admin", " ADMIN ", full_width("Admin")])
def test_username_variants_normalise_to_one_name(raw: str) -> None:
    assert USERNAME.validate_python(raw) == "admin"


@pytest.mark.parametrize("raw", ["ab", "x" * 51, "-admin", "admin-", "ad min", "ädmin", "a@b"])
def test_invalid_usernames_are_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        USERNAME.validate_python(raw)


@pytest.mark.parametrize("raw", ["Admin@Example.COM", " admin@example.com "])
def test_emails_are_lowercased_entirely(raw: str) -> None:
    assert EMAIL.validate_python(raw) == "admin@example.com"


@pytest.mark.parametrize("raw", ["not-an-email", "admin@", "@example.com"])
def test_invalid_emails_are_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        EMAIL.validate_python(raw)


def test_login_input_uses_the_same_normalisation() -> None:
    assert normalize_identifier(full_width("Admin")) == USERNAME.validate_python("admin")

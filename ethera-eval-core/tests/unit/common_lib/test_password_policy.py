"""Password policy: length, common passwords, and no reuse of the username or email.

Role: pins common_lib.schemas.password `validate_password`: `MIN_PASSWORD_LENGTH` to
  `MAX_PASSWORD_LENGTH` counted after NFKC normalisation, no composition rules, common passwords
  rejected case-insensitively, and no password equal to the username or email (full-width
  variants included).
Used by: pytest (unit).
Depends on: nothing beyond the module under test; no fixtures or services.
Key invariants: `WeakPasswordError` is a `ValueError`, so pydantic turns it into a 422 field
  error.
"""

import pytest

from common_lib.schemas.password import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    WeakPasswordError,
    validate_password,
)

USERNAME = "alice"
EMAIL = "alice.example@example.com"
STRONG_PASSWORD = "correct horse battery staple"


def check(password: str) -> None:
    validate_password(password, username=USERNAME, email=EMAIL)


def test_strong_password_is_accepted() -> None:
    check(STRONG_PASSWORD)


def test_no_composition_rules() -> None:
    # Lowercase letters only, but long and uncommon: accepted.
    check("lanternquietlymeadow")


@pytest.mark.parametrize("length", [MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH])
def test_boundary_lengths_are_accepted(length: int) -> None:
    check(("unpredictable-" * 10)[:length])


def test_too_short_is_rejected() -> None:
    with pytest.raises(WeakPasswordError, match="at least 12"):
        check("a" * (MIN_PASSWORD_LENGTH - 1))


def test_too_long_is_rejected() -> None:
    with pytest.raises(WeakPasswordError, match="at most 128"):
        check("a" * (MAX_PASSWORD_LENGTH + 1))


@pytest.mark.parametrize("password", ["qwerty123456", "QWERTY123456", "1q2w3e4r5t6y"])
def test_common_password_is_rejected_case_insensitively(password: str) -> None:
    with pytest.raises(WeakPasswordError, match="too common"):
        check(password)


@pytest.mark.parametrize("password", [EMAIL, EMAIL.upper()])
def test_password_equal_to_email_is_rejected(password: str) -> None:
    with pytest.raises(WeakPasswordError, match="username or email"):
        check(password)


def test_password_equal_to_username_is_rejected() -> None:
    long_username = "alice-the-administrator"
    with pytest.raises(WeakPasswordError, match="username or email"):
        validate_password(long_username.upper(), username=long_username, email=EMAIL)


def test_length_is_counted_after_nfkc_normalisation() -> None:
    # "ﬃ" is one character that NFKC expands to "ffi": four of them make 12 characters.
    check("ﬃ" * 4)

    with pytest.raises(WeakPasswordError, match="at least 12"):
        check("ﬃ" * 3 + "ab")


def test_full_width_username_is_recognised() -> None:
    long_username = "alice-the-administrator"
    full_width = "".join(chr(ord(c) + 0xFEE0) if c.isalpha() else c for c in long_username)

    with pytest.raises(WeakPasswordError, match="username or email"):
        validate_password(full_width, username=long_username, email=EMAIL)


def test_error_is_a_value_error() -> None:
    # Pydantic turns ValueError raised in validators into a 422 field error.
    assert issubclass(WeakPasswordError, ValueError)

"""Usernames and emails: one normalisation everywhere they enter the system.

Role: `normalize_identifier` and the `Username` / `Email` annotated types.
Used by: `backend.core.settings` (admin account), `backend.services.auth.service` (login),
  `backend.api.dependencies.rate_limit` (login key), `common_lib.schemas.users`;
  tests/unit/common_lib/test_identity.py.
Depends on: pydantic (`EmailStr`, validators), `unicodedata`.
Key invariants: both are compared case-insensitively: normalised to Unicode NFKC, stripped and
  lowercased at every boundary (account creation, login, settings, rate limit keys), so "Admin",
  "admin" and full-width "admin" are the same account. Emails are lowercased again after
  validation, because the validator may normalise the domain.
"""

import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, EmailStr, StringConstraints

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
# Letters, digits, dot, dash and underscore; starts and ends with a letter or digit.
USERNAME_PATTERN = r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$"


def normalize_identifier(value: str) -> str:
    """The canonical form of a username or email: NFKC, stripped, lowercase."""
    return unicodedata.normalize("NFKC", value).strip().lower()


def _normalize_input(value: object) -> object:
    return normalize_identifier(value) if isinstance(value, str) else value


Username = Annotated[
    str,
    BeforeValidator(_normalize_input),
    StringConstraints(
        min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH, pattern=USERNAME_PATTERN
    ),
]

# EmailStr keeps the local part's case; lowercase after validation as well, because
# the validator may normalise the domain.
Email = Annotated[EmailStr, BeforeValidator(_normalize_input), AfterValidator(str.lower)]

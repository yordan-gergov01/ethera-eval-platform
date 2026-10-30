"""Password policy, following NIST SP 800-63B.

Role: `validate_password` (12 to 128 characters, not commonly used, not equal to the username or
  email; no character-class rules), `normalize_password` and `WeakPasswordError`.
Used by: `backend.core.security` (normalisation before hashing), `backend.core.settings` (admin
  password), `backend.services.users.service`; tests/unit/common_lib/test_password_policy.py.
Depends on: the bundled `common_lib/schemas/data/common_passwords.txt`, `unicodedata`.
Key invariants: length matters, composition rules do not (template_core D-006). Passwords are
  normalised to NFKC before they are checked and before they are hashed or verified, so the same
  password typed on any keyboard is the same password. The error message is safe to show to the
  user. The common-password list is loaded once per process and is already lowercased.
"""

import unicodedata
from functools import cache
from importlib.resources import files

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

_COMMON_PASSWORDS_FILE = "data/common_passwords.txt"


class WeakPasswordError(ValueError):
    """The password does not meet the policy. The message is safe to show to the user."""


def normalize_password(password: str) -> str:
    """The canonical form of a password: Unicode NFKC. Used by the policy and the hasher."""
    return unicodedata.normalize("NFKC", password)


def validate_password(password: str, *, username: str, email: str) -> None:
    """Raise `WeakPasswordError` with a user-facing reason if the password is too weak."""
    password = normalize_password(password)
    username = normalize_password(username)
    email = normalize_password(email)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters long.")

    lowered = password.lower()
    if lowered in {username.lower(), email.lower()}:
        raise WeakPasswordError("Password must not be the same as the username or email.")
    if lowered in _common_passwords():
        raise WeakPasswordError("Password is too common. Choose a less predictable one.")


@cache
def _common_passwords() -> frozenset[str]:
    """Load the bundled list once per process; entries are already lowercased."""
    text = files("common_lib.schemas").joinpath(_COMMON_PASSWORDS_FILE).read_text(encoding="utf-8")
    return frozenset(
        line
        for line in (raw.strip() for raw in text.splitlines())
        if line and not line.startswith("#")
    )

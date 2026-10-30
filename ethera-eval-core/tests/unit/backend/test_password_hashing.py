"""Argon2id hashing: verification, NFKC normalisation and automatic hash upgrades.

Role: pins backend.core.security `Argon2PasswordHasher`: Argon2id hashes that verify and are
  salted, NFKC-equal passwords verify, outdated hashes are upgraded on a successful
  verification only, the dummy verification never succeeds, and the production parameters meet
  the OWASP minimum.
Used by: pytest (unit).
Depends on: pwdlib's `Argon2Hasher` with cheap parameters (the local `hasher` fixture). No
  services.
Key invariants: cheap parameters keep the tests fast, but one test checks the real production
  parameters; the plain password never appears in a hash.
"""

import pytest
from pwdlib.hashers.argon2 import Argon2Hasher

from backend.core.security import Argon2PasswordHasher

PASSWORD = "correct horse battery staple"

# Cheap parameters keep the tests fast; production uses the library defaults.
FAST = Argon2Hasher(time_cost=1, memory_cost=8192, parallelism=1)


@pytest.fixture
def hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher(FAST)


async def test_hash_is_argon2id_and_verifies(hasher: Argon2PasswordHasher) -> None:
    password_hash = await hasher.hash(PASSWORD)

    assert password_hash.startswith("$argon2id$")
    assert PASSWORD not in password_hash
    assert (await hasher.verify(PASSWORD, password_hash)).valid is True


async def test_wrong_password_does_not_verify(hasher: Argon2PasswordHasher) -> None:
    password_hash = await hasher.hash(PASSWORD)

    check = await hasher.verify("correct horse battery stapler", password_hash)

    assert check.valid is False
    assert check.upgraded_hash is None


async def test_same_password_hashes_differently(hasher: Argon2PasswordHasher) -> None:
    assert await hasher.hash(PASSWORD) != await hasher.hash(PASSWORD)


async def test_unicode_forms_of_the_same_password_are_equal(hasher: Argon2PasswordHasher) -> None:
    # Full-width letters (as typed with some input methods) normalise to ASCII under NFKC.
    full_width = "".join(chr(ord(c) + 0xFEE0) if c.isalpha() else c for c in "correct")
    password_hash = await hasher.hash(full_width + " horse battery staple")

    assert (await hasher.verify(PASSWORD, password_hash)).valid is True


async def test_outdated_hash_is_upgraded_on_successful_verification() -> None:
    old_hash = await Argon2PasswordHasher(Argon2Hasher(time_cost=1, memory_cost=8192)).hash(
        PASSWORD
    )
    current = Argon2PasswordHasher(Argon2Hasher(time_cost=2, memory_cost=8192))

    check = await current.verify(PASSWORD, old_hash)

    assert check.valid is True
    assert check.upgraded_hash is not None
    assert "t=2" in check.upgraded_hash
    assert (await current.verify(PASSWORD, check.upgraded_hash)).upgraded_hash is None


async def test_current_hash_is_not_upgraded(hasher: Argon2PasswordHasher) -> None:
    password_hash = await hasher.hash(PASSWORD)

    assert (await hasher.verify(PASSWORD, password_hash)).upgraded_hash is None


async def test_dummy_verification_does_real_work_and_never_succeeds(
    hasher: Argon2PasswordHasher,
) -> None:
    await hasher.verify_dummy(PASSWORD)
    await hasher.verify_dummy("not-a-real-password-only-for-timing")


async def test_production_parameters_are_argon2id_with_strong_settings() -> None:
    password_hash = await Argon2PasswordHasher().hash(PASSWORD)

    # $argon2id$v=19$m=<KiB>,t=<iterations>,p=<lanes>$<salt>$<hash>
    parameters = dict(item.split("=") for item in password_hash.split("$")[3].split(","))
    assert password_hash.startswith("$argon2id$")
    assert int(parameters["m"]) >= 19 * 1024  # OWASP minimum memory, in KiB
    assert int(parameters["t"]) >= 2

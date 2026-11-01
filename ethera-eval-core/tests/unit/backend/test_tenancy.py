"""The tenant setting's encoding, without a database.

Role: pins backend.dal.tenancy.transaction `encode_tenants`: distinct, sorted, comma-separated
  Client IDs; an empty set is the empty string; a bare string, an empty ID or an ID with the
  separator is refused.
Used by: pytest (unit).
Depends on: backend.dal.tenancy.transaction; no services.
Key invariants: the encoding is deterministic; nothing can smuggle a second Client ID into the
  set through the separator.
"""

import pytest

from backend.dal.tenancy.transaction import encode_tenants


def test_encode_tenants_distinct_and_sorted() -> None:
    assert encode_tenants(["beta", "acme", "beta"]) == "acme,beta"


def test_encode_tenants_empty_set_empty_string() -> None:
    assert encode_tenants([]) == ""


def test_encode_tenants_bare_string_refused() -> None:
    with pytest.raises(TypeError):
        encode_tenants("acme")


@pytest.mark.parametrize("client_id", ["", "acme,beta"])
def test_encode_tenants_empty_or_separator_refused(client_id: str) -> None:
    with pytest.raises(ValueError, match="slug"):
        encode_tenants([client_id])

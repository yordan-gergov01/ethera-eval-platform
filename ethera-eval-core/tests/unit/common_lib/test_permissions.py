"""The default grants match the agreed permission table exactly.

Role: pins common_lib.permissions `DEFAULT_ROLE_GRANTS` against an explicit expected table:
  every permission and every role is covered, plain users hold only `products:read`, and the
  permission codes are stable lowercase strings.
Used by: pytest (unit).
Depends on: nothing beyond the module under test; no fixtures or services.
Key invariants: the expected table is written out by hand, so any grant change must be made in
  the test too; the codes are stored in the database and shown in the API, so they must not
  drift.
"""

from common_lib.permissions import DEFAULT_ROLE_GRANTS, Permission, RoleName

EXPECTED_GRANTS = {
    Permission.USERS_READ: {RoleName.ADMIN},
    Permission.USERS_CREATE: {RoleName.ADMIN},
    Permission.USERS_UPDATE: {RoleName.ADMIN},
    Permission.PRODUCTS_READ: {RoleName.ADMIN, RoleName.USER},
    Permission.MANIFESTS_WRITE: {RoleName.ADMIN},
}


def test_every_permission_has_an_expected_grant() -> None:
    assert set(EXPECTED_GRANTS) == set(Permission)


def test_every_role_has_grants() -> None:
    assert set(DEFAULT_ROLE_GRANTS) == set(RoleName)


def test_grants_match_the_permission_table() -> None:
    actual = {
        permission: {role for role, granted in DEFAULT_ROLE_GRANTS.items() if permission in granted}
        for permission in Permission
    }
    assert actual == EXPECTED_GRANTS


def test_plain_users_hold_only_products_read() -> None:
    # Features that plain users may use add their grants with them (PP-003, slice 001).
    assert DEFAULT_ROLE_GRANTS[RoleName.USER] == frozenset({Permission.PRODUCTS_READ})


def test_permission_codes_are_stable_strings() -> None:
    # The codes are stored in the database and shown in the API, so they must not drift.
    assert Permission.USERS_UPDATE.value == "users:update"
    assert all(code.value == code.value.lower() for code in Permission)

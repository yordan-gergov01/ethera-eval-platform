"""Seeding: grants follow the code; the admin account is created once and never touched.

Role: pins backend.services.seeding `SeedingService.seed`: grants are synced from
  common_lib.permissions `DEFAULT_ROLE_GRANTS`, and the admin `AdminAccount` is created with a
  hashed password and the admin role only when no such account exists.
Used by: pytest (unit).
Depends on: local fakes `FakeGrants`, `FakeAccounts`, `FakeHasher` in place of the role and
  user repositories and the password hasher. No services.
Key invariants: an existing admin is never overwritten; seeding twice creates the admin once;
  the plain password never reaches the stored hash.
"""

from collections.abc import Iterable, Mapping

from pydantic import SecretStr

from backend.core.security import PasswordCheck
from backend.dal.users import NewUser
from backend.services.seeding import AdminAccount, SeedingService
from common_lib.permissions import DEFAULT_ROLE_GRANTS

ADMIN = AdminAccount(
    username="admin", email="admin@example.com", password=SecretStr("test-only-admin-password")
)


class FakeGrants:
    def __init__(self) -> None:
        self.synced: dict[str, set[str]] | None = None

    async def sync_grants(self, grants: Mapping[str, Iterable[str]]) -> None:
        self.synced = {role: set(codes) for role, codes in grants.items()}


class FakeAccounts:
    def __init__(self, existing: set[tuple[str, str]] | None = None) -> None:
        self.existing = existing or set()
        self.created: list[NewUser] = []

    async def exists(self, *, username: str, email: str) -> bool:
        return any(u == username or e == email for u, e in self.existing)

    async def create(self, user: NewUser) -> object:
        self.created.append(user)
        self.existing.add((user.username, user.email))
        return object()


class FakeHasher:
    async def hash(self, password: str) -> str:
        return f"hashed:{len(password)}"

    async def verify(self, password: str, password_hash: str) -> PasswordCheck:
        return PasswordCheck(valid=False)

    async def verify_dummy(self, password: str) -> None:
        return None


async def test_grants_are_synced_from_the_code() -> None:
    grants = FakeGrants()

    await SeedingService(grants, FakeAccounts(), FakeHasher()).seed(ADMIN)

    assert grants.synced == {
        role.value: {p.value for p in permissions}
        for role, permissions in DEFAULT_ROLE_GRANTS.items()
    }


async def test_admin_is_created_with_a_hashed_password_and_the_admin_role() -> None:
    accounts = FakeAccounts()

    await SeedingService(FakeGrants(), accounts, FakeHasher()).seed(ADMIN)

    [admin] = accounts.created
    assert admin.username == "admin"
    assert admin.email == "admin@example.com"
    assert admin.role_name == "admin"
    assert admin.password_hash.startswith("hashed:")
    assert "test-only-admin-password" not in admin.password_hash


async def test_existing_admin_is_never_overwritten() -> None:
    accounts = FakeAccounts(existing={("admin", "admin@example.com")})

    await SeedingService(FakeGrants(), accounts, FakeHasher()).seed(ADMIN)

    assert accounts.created == []


async def test_seeding_twice_creates_the_admin_once() -> None:
    accounts = FakeAccounts()
    service = SeedingService(FakeGrants(), accounts, FakeHasher())

    await service.seed(ADMIN)
    await service.seed(ADMIN)

    assert len(accounts.created) == 1

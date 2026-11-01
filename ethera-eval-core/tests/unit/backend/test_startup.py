"""Startup decisions that need no database: role attributes and the module-seed preconditions.

Role: pins backend.core.startup `role_problems` (every attribute that makes row security
  untrustworthy is reported) and `run_module_seeds` (registry order, the seed context, the
  refusal without a seeded administrator, nothing to do without seeds) and `append_only_tables`
  (the core's tables first, then each module's), with backend.core.modules `ModuleMount`
  refusing a table name that is not a plain lower-case identifier.
Used by: pytest (unit).
Depends on: backend.core.startup, backend.core.modules (`ModuleMount`, `SeedContext`); no
  services.
Key invariants: correct roles yield no problem; each wrong attribute yields its own problem;
  module seeds never run without the administrator they act as.
"""

from uuid import uuid4

import pytest

from backend.core.modules import ModuleMount, SeedContext
from backend.core.startup import (
    APPEND_ONLY_TABLES,
    RoleAttributes,
    StartupSeedError,
    append_only_tables,
    role_problems,
    run_module_seeds,
)

OWNER = RoleAttributes("owner", superuser=False, bypass_rls=True)
RUNTIME = RoleAttributes("runtime", superuser=False, bypass_rls=False)


def test_role_problems_correct_roles_none() -> None:
    assert role_problems(OWNER, RUNTIME, runtime_is_owner_member=False) == []


@pytest.mark.parametrize(
    ("owner", "runtime", "member", "problem"),
    [
        (None, RUNTIME, False, "migration owner role does not exist"),
        (RoleAttributes("owner", True, True), RUNTIME, False, "owner role must not be a superuser"),
        (RoleAttributes("owner", False, False), RUNTIME, False, "must have BYPASSRLS"),
        (OWNER, None, False, "runtime role does not exist"),
        (OWNER, RoleAttributes("runtime", True, False), False, "runtime role must not be a super"),
        (OWNER, RoleAttributes("runtime", False, True), False, "must not have BYPASSRLS"),
        (OWNER, RUNTIME, True, "must not be a member of the migration owner"),
    ],
)
def test_role_problems_each_wrong_attribute_reported(
    owner: RoleAttributes | None,
    runtime: RoleAttributes | None,
    member: bool,
    problem: str,
) -> None:
    problems = role_problems(owner, runtime, runtime_is_owner_member=member)

    assert len(problems) == 1
    assert problem in problems[0]


async def test_run_module_seeds_registry_order_with_the_admin_context() -> None:
    calls: list[tuple[str, SeedContext]] = []
    admin_id = uuid4()

    def recorder(name: str) -> ModuleMount:
        async def seed(context: SeedContext) -> None:
            calls.append((name, context))

        return ModuleMount(name=name, seed=seed)

    modules = [recorder("first"), ModuleMount(name="no_seed"), recorder("second")]
    await run_module_seeds(modules, admin_id, "admin")

    context = SeedContext(admin_user_id=admin_id, admin_username="admin")
    assert calls == [("first", context), ("second", context)]


async def test_run_module_seeds_without_admin_refuses() -> None:
    async def seed(context: SeedContext) -> None:
        raise AssertionError("must not run")

    with pytest.raises(StartupSeedError):
        await run_module_seeds([ModuleMount(name="seeded", seed=seed)], None, "admin")


async def test_run_module_seeds_without_seeds_needs_no_admin() -> None:
    await run_module_seeds([ModuleMount(name="plain")], None, "admin")


def test_append_only_tables_core_first_then_each_modules_own() -> None:
    modules = [
        ModuleMount(name="first", append_only_tables=("first_log",)),
        ModuleMount(name="plain"),
        ModuleMount(name="second", append_only_tables=("second_a", "second_b")),
    ]

    assert append_only_tables(modules) == (
        *APPEND_ONLY_TABLES,
        "first_log",
        "second_a",
        "second_b",
    )
    assert append_only_tables([]) == APPEND_ONLY_TABLES


@pytest.mark.parametrize("table", ["", "two words", "x; DROP TABLE users", "Upper", "1st"])
def test_module_mount_invalid_append_only_table_refused(table: str) -> None:
    with pytest.raises(ValueError, match="invalid table name"):
        ModuleMount(name="bad", append_only_tables=(table,))

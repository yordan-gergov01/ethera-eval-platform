"""Roles, permissions and their grants.

Role: `RoleRepository` stores the permission catalogue and the roles that hold permissions:
  `sync_grants` makes the database equal the grants defined in code; `grants` reads them back.
Used by: `backend.dal.roles` (re-export), and through it `backend.services.seeding.service`
  (startup sync) and `backend.services.roles.service`.
Depends on: Tortoise (`in_transaction`), `common_lib.models` (`PermissionRecord`, `Role`).
Key invariants: the sync is atomic. Permissions no longer defined in code are deleted with their
  grants; each role ends up with exactly its listed permissions. Roles are created but never
  deleted, because users may still hold them (template_core D-006).
"""

from collections.abc import Iterable, Mapping

from tortoise.transactions import in_transaction

from common_lib.models import PermissionRecord, Role


class RoleRepository:
    """Stores the permission catalogue and the roles that hold permissions."""

    async def sync_grants(self, grants: Mapping[str, Iterable[str]]) -> None:
        """Make the stored permissions and role grants equal `grants`, atomically.

        Permissions missing from the database are created and those no longer
        defined are deleted with their grants. Each role ends up with exactly the
        permissions listed for it. Roles are created but never deleted, because
        users may still hold them.
        """
        wanted = {role: set(codes) for role, codes in grants.items()}
        all_codes = set().union(*wanted.values()) if wanted else set()

        async with in_transaction():
            await PermissionRecord.filter(code__not_in=all_codes).delete()
            existing = {p.code: p for p in await PermissionRecord.filter(code__in=all_codes)}
            for code in all_codes - existing.keys():
                existing[code] = await PermissionRecord.create(code=code)

            for role_name, codes in wanted.items():
                role, _ = await Role.get_or_create(name=role_name)
                await role.permissions.clear()
                await role.permissions.add(*(existing[code] for code in sorted(codes)))

    async def grants(self) -> dict[str, set[str]]:
        """The stored grants, by role name."""
        roles = await Role.all().prefetch_related("permissions")
        return {role.name: {p.code for p in role.permissions} for role in roles}

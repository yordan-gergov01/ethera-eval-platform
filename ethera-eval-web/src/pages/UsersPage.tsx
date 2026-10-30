/**
 * Page with the list of users.
 *
 * Role: composes UsersList under a heading.
 * Used by: routes/router.tsx (users).
 * Depends on: features/users/UsersList.
 * Key invariants: the users:read check lives in the router (RequirePermission), not here.
 */
import { UsersList } from '@/features/users/UsersList';

export function UsersPage() {
  return (
    <>
      <h1>Users</h1>
      <UsersList />
    </>
  );
}

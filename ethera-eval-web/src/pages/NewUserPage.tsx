/**
 * Page for creating a user.
 *
 * Role: composes CreateUserForm with a link back to the list.
 * Used by: routes/router.tsx (users/new).
 * Depends on: features/users/CreateUserForm, react-router Link.
 * Key invariants: the users:create check lives in the router (RequirePermission), not here.
 */
import { Link } from 'react-router';

import { CreateUserForm } from '@/features/users/CreateUserForm';

export function NewUserPage() {
  return (
    <>
      <p>
        <Link to="/users">Back to users</Link>
      </p>
      <h1>Create user</h1>
      <CreateUserForm />
    </>
  );
}

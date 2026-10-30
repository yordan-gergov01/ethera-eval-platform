/**
 * Page for one user.
 *
 * Role: reads the user id from the URL and composes UserDetail with a link back to the list.
 * Used by: routes/router.tsx (users/:userId).
 * Depends on: features/users/UserDetail, react-router useParams and Link.
 * Key invariants: UserDetail is keyed by userId so moving between users resets its state; the
 *   users:read check lives in the router.
 */
import { Link, useParams } from 'react-router';

import { UserDetail } from '@/features/users/UserDetail';

export function UserDetailPage() {
  const { userId = '' } = useParams();

  return (
    <>
      <p>
        <Link to="/users">Back to users</Link>
      </p>
      <h1>User</h1>
      <UserDetail key={userId} userId={userId} />
    </>
  );
}

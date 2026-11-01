/**
 * Paged table of users with previous and next controls.
 *
 * Role: list view of the users feature, with a "Create user" link for users:create.
 * Used by: pages/UsersPage.tsx.
 * Depends on: ./use-users-page, ./labels (role labels), ErrorMessage, useAuth().can,
 *   react-router Link.
 * Key invariants: while the next page loads the current one stays visible (aria-busy) and "Next" is
 *   disabled; the create link is hidden without users:create (cosmetic: the route guard and the
 *   backend also check).
 */
import { Link } from 'react-router';

import { roleLabel } from './labels';
import { useUsersPage } from './use-users-page';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useAuth } from '@/providers/auth/auth-context';

/** One page of users with paging controls. */
export function UsersList() {
  const { can } = useAuth();
  const { query, page, pages, goTo } = useUsersPage();
  const { data, error, isPending, isPlaceholderData } = query;

  if (isPending) {
    return <p className="status">Loading…</p>;
  }
  if (error) {
    return <ErrorMessage error={error} />;
  }

  return (
    <>
      {can('users:create') && (
        <p>
          <Link to="/users/new">Create user</Link>
        </p>
      )}
      <div className="overflow-x-auto">
        <table aria-busy={isPlaceholderData}>
          <thead>
            <tr>
              <th scope="col">Username</th>
              <th scope="col">Name</th>
              <th scope="col">Email</th>
              <th scope="col">Role</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((user) => (
              <tr key={user.id}>
                <td>
                  <Link to={`/users/${user.id}`}>{user.username}</Link>
                </td>
                <td>{user.full_name}</td>
                <td>{user.email}</td>
                <td>{roleLabel(user.role)}</td>
                <td>{user.is_active ? 'Active' : 'Inactive'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <nav aria-label="Pages" className="pagination">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => {
            goTo(page - 1);
          }}
        >
          Previous
        </button>
        <span>
          Page {page} of {pages} ({data.total} users)
        </span>
        <button
          type="button"
          disabled={page >= pages || isPlaceholderData}
          onClick={() => {
            goTo(page + 1);
          }}
        >
          Next
        </button>
      </nav>
    </>
  );
}

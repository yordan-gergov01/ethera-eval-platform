/**
 * Route guard for pages that need a signed-in user.
 *
 * Role: lets signed-in users through and sends everyone else to the login page.
 * Used by: routes/router.tsx.
 * Depends on: useAuth, ErrorMessage, react-router Navigate/Outlet/useLocation, LoginLocationState.
 * Key invariants: anonymous users go to /login with path, query and hash in state.from so they
 *   return afterwards; a failed user load shows the error with "Try again" instead of ending the
 *   session.
 */
import { Navigate, Outlet, useLocation } from 'react-router';

import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { useAuth } from '@/providers/auth/auth-context';
import type { LoginLocationState } from '@/types/navigation';

/** Lets signed-in users through; sends everyone else to the login page and back afterwards. */
export function RequireAuth() {
  const { status, error, retry } = useAuth();
  const location = useLocation();

  if (status === 'anonymous') {
    const state: LoginLocationState = {
      from: `${location.pathname}${location.search}${location.hash}`,
    };
    return <Navigate to="/login" replace state={state} />;
  }
  if (status === 'loading') {
    return <p className="status">Loading…</p>;
  }
  if (status === 'error') {
    return (
      <main>
        <ErrorMessage error={error} />
        <button type="button" onClick={retry}>
          Try again
        </button>
      </main>
    );
  }
  return <Outlet />;
}

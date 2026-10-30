/**
 * Router state shared between the auth guard and the login page.
 *
 * Role: types the state RequireAuth passes to /login.
 * Used by: routes/RequireAuth.tsx, pages/LoginPage.tsx.
 * Depends on: nothing; types only.
 * Key invariants: `from` holds path, query and hash together.
 */
/** Router state passed to the login page when a signed-out user opens a protected page. */
export interface LoginLocationState {
  /** The page to return to after signing in (path, query and hash). */
  from?: string;
}

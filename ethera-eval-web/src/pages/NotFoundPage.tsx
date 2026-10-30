/**
 * Page for unknown paths.
 *
 * Role: static "Page not found" message with a link to the start page.
 * Used by: routes/router.tsx (catch-all '*' route).
 * Depends on: react-router Link.
 * Key invariants: the catch-all route sits inside RequireAuth and the app shell, so only signed-in
 *   users see it.
 */
import { Link } from 'react-router';

export function NotFoundPage() {
  return (
    <>
      <h1>Page not found</h1>
      <p>
        This page does not exist. <Link to="/">Go to the start page</Link>.
      </p>
    </>
  );
}

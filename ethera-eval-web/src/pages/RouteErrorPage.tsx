/**
 * Page the router shows when a route fails to render.
 *
 * Role: error element of the root route.
 * Used by: routes/router.tsx (errorElement).
 * Depends on: react-router useRouteError.
 * Key invariants: the error message is shown only in development builds.
 */
import { useRouteError } from 'react-router';

/** Shown by the router when a page fails to render. */
export function RouteErrorPage() {
  const error = useRouteError();

  return (
    <main>
      <h1>Something went wrong</h1>
      <p>The page could not be displayed. Reload the page to try again.</p>
      {import.meta.env.DEV && error instanceof Error && <pre>{error.message}</pre>}
    </main>
  );
}

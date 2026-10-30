/**
 * Fallback screen of the top-level error boundary.
 *
 * Role: replaces a blank page with "Something went wrong" and a "Try again" button that resets the
 *   boundary.
 * Used by: src/App.tsx (ErrorBoundary FallbackComponent).
 * Depends on: react-error-boundary FallbackProps.
 * Key invariants: the error message is shown only in development (import.meta.env.DEV), never in
 *   production builds.
 */
import type { FallbackProps } from 'react-error-boundary';

/** Shown by the top-level error boundary instead of a blank page when rendering fails. */
export function AppErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <main>
      <h1>Something went wrong</h1>
      <p>The page could not be displayed.</p>
      {import.meta.env.DEV && error instanceof Error && <pre>{error.message}</pre>}
      <button type="button" onClick={resetErrorBoundary}>
        Try again
      </button>
    </main>
  );
}

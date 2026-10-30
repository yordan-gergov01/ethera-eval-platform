/**
 * Root component: top-level error boundary around the app providers and the router.
 *
 * Role: composes the whole app once: ErrorBoundary > AppProviders > RouterProvider.
 * Used by: src/main.tsx.
 * Depends on: react-error-boundary, react-router/dom RouterProvider, AppErrorFallback,
 *   AppProviders, routes/router.
 * Key invariants: the boundary wraps the providers too, so a crash there still shows
 *   AppErrorFallback instead of a blank page; render errors are logged to the console only in
 *   development.
 */
import type { ErrorInfo } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { RouterProvider } from 'react-router/dom';

import { AppErrorFallback } from '@/components/layout/AppErrorFallback';
import { AppProviders } from '@/providers/AppProviders';
import { router } from '@/routes/router';

function reportRenderError(error: unknown, info: ErrorInfo) {
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console -- development-only diagnostics
    console.error(error, info.componentStack);
  }
}

export function App() {
  return (
    <ErrorBoundary FallbackComponent={AppErrorFallback} onError={reportRenderError}>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </ErrorBoundary>
  );
}

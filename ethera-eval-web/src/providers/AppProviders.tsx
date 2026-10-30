/**
 * App-wide providers: the TanStack Query client and the session.
 *
 * Role: wraps the router in QueryClientProvider and AuthProvider.
 * Used by: src/App.tsx.
 * Depends on: QueryClientProvider, createQueryClient (lib/query-client),
 *   providers/auth/AuthProvider.
 * Key invariants: the QueryClient is created once per mount (useState initialiser); AuthProvider
 *   sits inside QueryClientProvider because it uses the query client.
 */
import { QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

import { AuthProvider } from '@/providers/auth/AuthProvider';
import { createQueryClient } from '@/lib/query-client';

export interface AppProvidersProps {
  children: ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

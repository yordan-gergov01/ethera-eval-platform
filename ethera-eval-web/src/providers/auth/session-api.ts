/**
 * Backend calls of the session: login, logout and the current-user query.
 *
 * Role: the requests AuthProvider builds the session on.
 * Used by: providers/auth/AuthProvider.tsx, features/profile/use-update-profile.ts,
 *   features/users/use-update-user.ts, session-api.test.ts.
 * Depends on: api from lib/api/http; POST /api/v1/auth/login (form body), POST /api/v1/auth/logout,
 *   GET /api/v1/users/me.
 * Key invariants: the login request sends no token (auth: false), so its 401 never ends a session;
 *   the `me` query never reports a 403, because it is what a reported 403 reloads; logout ends
 *   every session of the user on the backend.
 */
import { queryOptions } from '@tanstack/react-query';

import { api } from '@/lib/api/http';
import type { Me, Token } from '@/lib/api/types';

export function loginRequest(username: string, password: string) {
  return api.post<Token>('/api/v1/auth/login', { form: { username, password }, auth: false });
}

/** Ends every session of the user on the backend. */
export function logoutRequest() {
  return api.post<undefined>('/api/v1/auth/logout');
}

export const meQueryOptions = queryOptions({
  queryKey: ['me'],
  // Never reports a 403: this query is what a reported 403 reloads.
  queryFn: ({ signal }) => api.get<Me>('/api/v1/users/me', { signal, reportForbidden: false }),
  staleTime: 60_000,
});

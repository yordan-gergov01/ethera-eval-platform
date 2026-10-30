/**
 * Mutation hook that signs in through the auth context.
 *
 * Role: wraps AuthContext.login in a TanStack mutation for the form's pending and error state.
 * Used by: features/auth/LoginForm.tsx.
 * Depends on: @tanstack/react-query useMutation, useAuth from providers/auth/auth-context.
 * Key invariants: the username is trimmed, the password is passed as typed; never retried
 *   (lib/query-client.ts); the redirect after success is done by LoginPage, not here.
 */
import { useMutation } from '@tanstack/react-query';

import { useAuth } from '@/providers/auth/auth-context';

export interface Credentials {
  username: string;
  password: string;
}

/** Signs in and loads the user; the login page then moves on. */
export function useLogin() {
  const { login } = useAuth();
  return useMutation({
    mutationFn: ({ username, password }: Credentials) => login(username.trim(), password),
  });
}

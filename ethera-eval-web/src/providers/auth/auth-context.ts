/**
 * Session context: its type, the context object and the useAuth hook.
 *
 * Role: the contract between AuthProvider and every component that reads the session.
 * Used by: providers/auth/AuthProvider.tsx, components/layout/AppShell.tsx, features auth, profile
 *   and users, pages LoginPage and ProfilePage, routes RequireAuth and RequirePermission.
 * Depends on: React createContext and useContext; Me and Permission types.
 * Key invariants: useAuth throws outside AuthProvider; logout ends every session on the backend
 *   while endSession only clears local state; endReason null means the user logged out themselves.
 */
import { createContext, useContext } from 'react';

import type { Me, Permission } from '@/lib/api/types';

/**
 * anonymous: no token. loading: token present, user not loaded yet.
 * authenticated: user loaded. error: the user could not be loaded (for
 * example the backend is unreachable); `retry` tries again.
 */
export type AuthStatus = 'anonymous' | 'loading' | 'authenticated' | 'error';

/** Why the last session ended without the user logging out; shown on the login page. */
export type SessionEndReason = 'expired' | 'unauthorized' | 'password-changed';

export interface AuthContextValue {
  status: AuthStatus;
  user: Me | null;
  error: unknown;
  endReason: SessionEndReason | null;
  can: (permission: Permission) => boolean;
  /** Signs in and loads the user. Rejects with the ApiError of a failed login. */
  login: (username: string, password: string) => Promise<void>;
  /** Ends every session on the backend, then clears local state whatever the result. */
  logout: () => Promise<void>;
  /** Clears local state only, after the backend has already ended the session. */
  endSession: (reason: SessionEndReason | null) => void;
  retry: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return value;
}

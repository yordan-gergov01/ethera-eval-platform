/**
 * Session provider: token, current user, permissions, login, logout and session end.
 *
 * Role: owns the session state behind useAuth (template_web D-001, D-003).
 * Used by: providers/AppProviders.tsx.
 * Depends on: lib/token-storage (useSyncExternalStore), ./session-api, handler registration in
 *   lib/api/http, ./permissions, TanStack Query; POST /api/v1/auth/login, POST /api/v1/auth/logout,
 *   GET /api/v1/users/me.
 * Key invariants: the session ends 30 s before the token expires, on any 401 to a request that
 *   carried the token, and on logout (template_web D-003); ending a session clears the token and
 *   the whole query cache; logout clears local state whatever the backend answers; a reported 403
 *   reloads `me`; the expiry timer is clamped to the setTimeout maximum; callbacks and the context
 *   value are memoised so they change only when the session does.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react';

import { AuthContext, type AuthContextValue, type SessionEndReason } from './auth-context';
import { hasPermission } from './permissions';
import { loginRequest, logoutRequest, meQueryOptions } from './session-api';
import { setForbiddenHandler, setUnauthorizedHandler } from '@/lib/api/http';
import type { Permission } from '@/lib/api/types';
import { EXPIRY_MARGIN_MS, tokenStorage } from '@/lib/token-storage';

// setTimeout fires at once for delays above this (about 24.8 days).
const MAX_TIMEOUT_MS = 2 ** 31 - 1;

export interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient();
  const stored = useSyncExternalStore(tokenStorage.subscribe, tokenStorage.get);
  const [endReason, setEndReason] = useState<SessionEndReason | null>(null);

  const me = useQuery({ ...meQueryOptions, enabled: stored !== null });

  // useCallback and useMemo below are referential: the context value reaches
  // every page, so it must change only when the session does, and endSession is
  // a dependency of the effects that register the 401 handler and the timer.
  const endSession = useCallback(
    (reason: SessionEndReason | null) => {
      tokenStorage.clear();
      queryClient.clear();
      setEndReason(reason);
    },
    [queryClient],
  );

  // Any 401 on a request that carried the token ends the session.
  useEffect(
    () =>
      setUnauthorizedHandler(() => {
        endSession('unauthorized');
      }),
    [endSession],
  );

  // A refused request may mean the user's permissions changed: reload them so
  // the navigation catches up. The reload itself never reports a 403.
  useEffect(
    () =>
      setForbiddenHandler(() => {
        void queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey });
      }),
    [queryClient],
  );

  // End the session shortly before the token expires.
  useEffect(() => {
    if (!stored) {
      return;
    }
    const delay = stored.expiresAt - EXPIRY_MARGIN_MS - Date.now();
    const timer = setTimeout(
      () => {
        endSession('expired');
      },
      Math.min(Math.max(delay, 0), MAX_TIMEOUT_MS),
    );
    return () => {
      clearTimeout(timer);
    };
  }, [stored, endSession]);

  const login = useCallback(
    async (username: string, password: string) => {
      const token = await loginRequest(username, password);
      queryClient.clear();
      setEndReason(null);
      tokenStorage.set(token.access_token, token.expires_in);
      await queryClient.query(meQueryOptions);
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // The local session ends whatever the backend answered.
    }
    endSession(null);
  }, [endSession]);

  const user = me.data ?? null;
  const can = useCallback(
    (permission: Permission) => hasPermission(user?.permissions, permission),
    [user],
  );
  const { refetch } = me;
  const retry = useCallback(() => {
    void refetch();
  }, [refetch]);

  let status: AuthContextValue['status'] = 'loading';
  if (stored === null) {
    status = 'anonymous';
  } else if (user) {
    status = 'authenticated';
  } else if (me.isError) {
    status = 'error';
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      error: me.error,
      endReason,
      can,
      login,
      logout,
      endSession,
      retry,
    }),
    [status, user, me.error, endReason, can, login, logout, endSession, retry],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

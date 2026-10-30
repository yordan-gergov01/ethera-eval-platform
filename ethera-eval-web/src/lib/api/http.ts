/**
 * The app's single configured API client and its session hooks.
 *
 * Role: wires createApiClient to the runtime config and the token storage; lets the session
 *   provider register 401 and 403 handlers.
 * Used by: features/profile/api.ts, features/users/api.ts, providers/auth/session-api.ts,
 *   providers/auth/AuthProvider.tsx (handlers), session-api.test.ts (mocked).
 * Depends on: ./client, config/runtime-config (backend URL), lib/token-storage (token).
 * Key invariants: every backend call in the app goes through `api`; base URL and token are read per
 *   request (template_web D-004); the handlers are no-ops until AuthProvider registers them, and
 *   the returned function unregisters them.
 */
import { createApiClient } from './client';
import { getRuntimeConfig } from '@/config/runtime-config';
import { tokenStorage } from '@/lib/token-storage';

let unauthorizedHandler: () => void = () => undefined;

/**
 * Registers what happens when the backend rejects the token (the session
 * provider ends the session). Returns a function that removes the handler.
 */
export function setUnauthorizedHandler(handler: () => void) {
  unauthorizedHandler = handler;
  return () => {
    unauthorizedHandler = () => undefined;
  };
}

let forbiddenHandler: () => void = () => undefined;

/**
 * Registers what happens when a request is refused for a missing permission
 * (the session provider reloads the permissions). Returns a function that
 * removes the handler.
 */
export function setForbiddenHandler(handler: () => void) {
  forbiddenHandler = handler;
  return () => {
    forbiddenHandler = () => undefined;
  };
}

/** The client every backend call in the app uses. */
export const api = createApiClient({
  baseUrl: () => getRuntimeConfig().backendUrl,
  getToken: () => tokenStorage.getToken(),
  onUnauthorized: () => {
    unauthorizedHandler();
  },
  onForbidden: () => {
    forbiddenHandler();
  },
});

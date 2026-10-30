/**
 * The access token of this browser tab, kept in sessionStorage.
 *
 * Role: stores the token and its expiry, hands it out while usable and notifies subscribers; the
 *   session state built on it lives in providers/auth.
 * Used by: lib/api/http.ts (token per request), providers/auth/AuthProvider.tsx (subscription and
 *   expiry timer), token-storage.test.ts.
 * Depends on: window.sessionStorage under the key 'ethera-eval.session', Date.now.
 * Key invariants: sessionStorage so the token survives a reload but not the tab (template_web
 *   D-003); a token within EXPIRY_MARGIN_MS (30 s) of expiry is never sent and is dropped on load;
 *   storage errors are swallowed (the session then lasts until a reload); `get` returns the same
 *   object until the next change, as useSyncExternalStore requires.
 */

export interface StoredToken {
  token: string;
  /** When the backend stops accepting the token, in milliseconds since the epoch. */
  expiresAt: number;
}

/** The session ends this long before the token expires, so no request is sent with a token about to expire. */
export const EXPIRY_MARGIN_MS = 30_000;

const STORAGE_KEY = 'ethera-eval.session';

function isStoredToken(value: unknown): value is StoredToken {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const { token, expiresAt } = value as Record<string, unknown>;
  return typeof token === 'string' && token !== '' && typeof expiresAt === 'number';
}

export function createTokenStorage(storage: Storage | undefined, now: () => number = Date.now) {
  const listeners = new Set<() => void>();

  const isUsable = (stored: StoredToken) => now() < stored.expiresAt - EXPIRY_MARGIN_MS;

  function write(value: StoredToken | null) {
    try {
      if (value) {
        storage?.setItem(STORAGE_KEY, JSON.stringify(value));
      } else {
        storage?.removeItem(STORAGE_KEY);
      }
    } catch {
      // Storage can be full or blocked; the session then lasts until a reload.
    }
  }

  function readInitial(): StoredToken | null {
    let parsed: unknown;
    try {
      parsed = JSON.parse(storage?.getItem(STORAGE_KEY) ?? 'null');
    } catch {
      parsed = null;
    }
    if (isStoredToken(parsed) && isUsable(parsed)) {
      return parsed;
    }
    write(null);
    return null;
  }

  let current = readInitial();

  function update(value: StoredToken | null) {
    current = value;
    write(value);
    listeners.forEach((listener) => {
      listener();
    });
  }

  return {
    /** The stored token, also once it is near expiry; stable between changes. */
    get: (): StoredToken | null => current,
    /** The token to send, or null when there is none or it is about to expire. */
    getToken: (): string | null => (current && isUsable(current) ? current.token : null),
    set: (token: string, expiresInSeconds: number) => {
      update({ token, expiresAt: now() + expiresInSeconds * 1000 });
    },
    clear: () => {
      if (current !== null) {
        update(null);
      }
    },
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

export type TokenStorage = ReturnType<typeof createTokenStorage>;

function sessionStorageOrUndefined(): Storage | undefined {
  try {
    return typeof window === 'undefined' ? undefined : window.sessionStorage;
  } catch {
    // Access is denied when the browser blocks site storage.
    return undefined;
  }
}

export const tokenStorage = createTokenStorage(sessionStorageOrUndefined());

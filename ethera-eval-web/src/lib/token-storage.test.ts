/**
 * Unit tests for the tab-scoped token store.
 *
 * Role: proves storing, restoring, expiry handling, clearing and change notification.
 * Used by: Vitest.
 * Depends on: ./token-storage, an in-memory Storage and an injected clock.
 * Key invariants: pins the 30 s expiry margin and the storage key 'ethera-eval.session'.
 */
import { describe, expect, it, vi } from 'vitest';

import { EXPIRY_MARGIN_MS, createTokenStorage } from './token-storage';

const KEY = 'ethera-eval.session';

class MemoryStorage implements Storage {
  private items = new Map<string, string>();

  get length() {
    return this.items.size;
  }

  clear() {
    this.items.clear();
  }

  getItem(key: string) {
    return this.items.get(key) ?? null;
  }

  key(index: number) {
    return [...this.items.keys()][index] ?? null;
  }

  removeItem(key: string) {
    this.items.delete(key);
  }

  setItem(key: string, value: string) {
    this.items.set(key, value);
  }
}

function clock(start = 1_000_000) {
  let time = start;
  return {
    now: () => time,
    advance: (ms: number) => {
      time += ms;
    },
  };
}

describe('createTokenStorage', () => {
  it('stores the token with its expiry time', () => {
    const storage = new MemoryStorage();
    const { now } = clock();
    const tokens = createTokenStorage(storage, now);

    tokens.set('abc', 1800);

    expect(tokens.get()).toEqual({ token: 'abc', expiresAt: now() + 1_800_000 });
    expect(tokens.getToken()).toBe('abc');
    expect(JSON.parse(storage.getItem(KEY) ?? 'null')).toEqual({
      token: 'abc',
      expiresAt: now() + 1_800_000,
    });
  });

  it('restores a stored token that is still valid', () => {
    const storage = new MemoryStorage();
    const { now } = clock();
    storage.setItem(KEY, JSON.stringify({ token: 'abc', expiresAt: now() + 600_000 }));

    expect(createTokenStorage(storage, now).getToken()).toBe('abc');
  });

  it('drops a stored token that is expired or about to expire', () => {
    const storage = new MemoryStorage();
    const { now } = clock();
    storage.setItem(KEY, JSON.stringify({ token: 'abc', expiresAt: now() + EXPIRY_MARGIN_MS }));

    const tokens = createTokenStorage(storage, now);

    expect(tokens.get()).toBeNull();
    expect(storage.getItem(KEY)).toBeNull();
  });

  it.each(['not json', '{"token":42,"expiresAt":1}', '{"token":"","expiresAt":1}', '[]'])(
    'drops a corrupt stored value %j',
    (value) => {
      const storage = new MemoryStorage();
      storage.setItem(KEY, value);

      expect(createTokenStorage(storage).get()).toBeNull();
      expect(storage.getItem(KEY)).toBeNull();
    },
  );

  it('stops handing out the token within the expiry margin', () => {
    const { now, advance } = clock();
    const tokens = createTokenStorage(new MemoryStorage(), now);
    tokens.set('abc', 60);

    advance(60_000 - EXPIRY_MARGIN_MS - 1);
    expect(tokens.getToken()).toBe('abc');
    advance(1);
    expect(tokens.getToken()).toBeNull();
    expect(tokens.get()).not.toBeNull();
  });

  it('clears the token and the stored value', () => {
    const storage = new MemoryStorage();
    const tokens = createTokenStorage(storage);
    tokens.set('abc', 1800);

    tokens.clear();

    expect(tokens.get()).toBeNull();
    expect(tokens.getToken()).toBeNull();
    expect(storage.getItem(KEY)).toBeNull();
  });

  it('notifies listeners of changes until they unsubscribe', () => {
    const tokens = createTokenStorage(new MemoryStorage());
    const listener = vi.fn();
    const unsubscribe = tokens.subscribe(listener);

    tokens.set('abc', 1800);
    tokens.clear();
    tokens.clear();
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    tokens.set('def', 1800);
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it('works without storage', () => {
    const tokens = createTokenStorage(undefined);
    tokens.set('abc', 1800);
    expect(tokens.getToken()).toBe('abc');
  });
});

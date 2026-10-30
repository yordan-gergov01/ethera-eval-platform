/**
 * Unit test for the current-user query.
 *
 * Role: proves the `me` query opts out of 403 reporting.
 * Used by: Vitest.
 * Depends on: ./session-api, vi.mock of @/lib/api/http.
 * Key invariants: pins "never reports a 403, so reloading the permissions cannot trigger another
 *   reload".
 */
import { describe, expect, it, vi } from 'vitest';

import { meQueryOptions } from './session-api';
import { api } from '@/lib/api/http';

vi.mock('@/lib/api/http', () => ({ api: { get: vi.fn(() => Promise.resolve({})) } }));

describe('meQueryOptions', () => {
  it('never reports a 403, so reloading the permissions cannot trigger another reload', async () => {
    const signal = new AbortController().signal;
    const queryFn = meQueryOptions.queryFn;
    if (typeof queryFn !== 'function') {
      throw new Error('queryFn missing');
    }

    // Only the signal is read from the query context.
    await queryFn({ signal } as Parameters<typeof queryFn>[0]);

    expect(vi.mocked(api.get)).toHaveBeenCalledWith('/api/v1/users/me', {
      signal,
      reportForbidden: false,
    });
  });
});

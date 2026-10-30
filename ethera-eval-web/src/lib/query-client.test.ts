/**
 * Unit tests for the TanStack Query defaults.
 *
 * Role: proves the retry policy of queries and mutations.
 * Used by: Vitest.
 * Depends on: ./query-client, ApiError and NetworkError.
 * Key invariants: pins "never retries mutations".
 */
import { describe, expect, it } from 'vitest';

import { ApiError, NetworkError } from '@/lib/api/errors';
import { MAX_QUERY_RETRIES, createQueryClient, retryDelay, shouldRetryQuery } from './query-client';

function apiError(status: number, retryAfter?: number) {
  return new ApiError({ status, code: 'X', title: 'X', detail: 'X', retryAfter });
}

describe('createQueryClient', () => {
  it('never retries mutations', () => {
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(0);
  });

  it('retries queries with shouldRetryQuery and retryDelay', () => {
    const queries = createQueryClient().getDefaultOptions().queries;
    expect(queries?.retry).toBe(shouldRetryQuery);
    expect(queries?.retryDelay).toBe(retryDelay);
  });
});

describe('shouldRetryQuery', () => {
  it.each([
    ['a network error', new NetworkError(new TypeError('Failed to fetch')), true],
    ['a 500', apiError(500), true],
    ['a 503', apiError(503), true],
    ['a 400', apiError(400), false],
    ['a 401', apiError(401), false],
    ['a 403', apiError(403), false],
    ['a 404', apiError(404), false],
    ['a 429', apiError(429), false],
    ['any other error', new Error('bug'), false],
  ])('after %s: %s', (_label, error, expected) => {
    expect(shouldRetryQuery(0, error)).toBe(expected);
  });

  it(`stops after ${String(MAX_QUERY_RETRIES)} retries`, () => {
    const error = apiError(503);
    expect(shouldRetryQuery(MAX_QUERY_RETRIES - 1, error)).toBe(true);
    expect(shouldRetryQuery(MAX_QUERY_RETRIES, error)).toBe(false);
  });
});

describe('retryDelay', () => {
  it('backs off exponentially up to 10 seconds', () => {
    const error = new NetworkError(new TypeError('Failed to fetch'));
    expect([0, 1, 2, 3, 4, 5].map((attempt) => retryDelay(attempt, error))).toEqual([
      1000, 2000, 4000, 8000, 10_000, 10_000,
    ]);
  });

  it('follows Retry-After', () => {
    expect(retryDelay(0, apiError(503, 3))).toBe(3000);
  });
});

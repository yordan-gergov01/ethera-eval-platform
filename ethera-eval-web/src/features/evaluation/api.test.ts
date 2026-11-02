/**
 * Unit tests for the evaluation feature's backend calls.
 *
 * Role: proves the paths and URL encoding of the Dataset summary and Dataset version reads, the
 *   query keys, and that DATASET_NOT_FOUND and DATASET_VERSION_NOT_FOUND arrive as ApiErrors with
 *   their codes.
 * Used by: Vitest.
 * Depends on: ./api (with lib/api/http's `api` driven through a stubbed global fetch),
 *   lib/api/errors, config/runtime-config (stubbed window config).
 * Key invariants: every path segment is URL-encoded, the version too; a non-numeric version is
 *   sent to the backend as given (never parsed in the browser); both reads are GETs.
 */
import { QueryClient } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  DATASET_KEY,
  datasetPath,
  datasetSummaryQueryOptions,
  datasetVersionPath,
  datasetVersionQueryOptions,
} from './api';
import { ApiError } from '@/lib/api/errors';

const BACKEND = 'http://backend:8000';

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function problem(status: number, code: string) {
  return new Response(
    JSON.stringify({ title: 'Not Found', status, detail: 'Not found.', code, request_id: 'r-1' }),
    { status, headers: { 'Content-Type': 'application/problem+json' } },
  );
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>(() => Promise.resolve(json({})));
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('window', { __APP_CONFIG__: { backendUrl: BACKEND } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function lastCall() {
  const call = fetchMock.mock.lastCall;
  if (!call) {
    throw new Error('fetch was not called');
  }
  const [url, init = {}] = call;
  const href = typeof url === 'string' ? url : url instanceof URL ? url.href : url.url;
  return { url: new URL(href), init };
}

const queryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe('evaluation backend paths', () => {
  it('builds the Dataset path with URL-encoded identifiers', () => {
    expect(datasetPath('acme', 'support-bot')).toBe('/api/v1/products/acme/support-bot/dataset');
    expect(datasetPath('a/b', 'c d')).toBe('/api/v1/products/a%2Fb/c%20d/dataset');
  });

  it('URL-encodes the version segment as given', () => {
    expect(datasetVersionPath('acme', 'support-bot', '2')).toBe(
      '/api/v1/products/acme/support-bot/dataset/versions/2',
    );
    expect(datasetVersionPath('acme', 'support-bot', '1/../x?y')).toBe(
      '/api/v1/products/acme/support-bot/dataset/versions/1%2F..%2Fx%3Fy',
    );
  });
});

describe('evaluation api', () => {
  it('reads the Dataset summary', async () => {
    const summary = { client_id: 'acme', project_id: 'support-bot', current_version: 1 };
    fetchMock.mockResolvedValueOnce(json(summary));

    const result = await queryClient().query(datasetSummaryQueryOptions('acme', 'a/b c'));

    expect(result).toEqual(summary);
    const { url, init } = lastCall();
    expect(init.method).toBe('GET');
    expect(url.origin + url.pathname).toBe(`${BACKEND}/api/v1/products/acme/a%2Fb%20c/dataset`);
    expect(url.search).toBe('');
  });

  it('reads one Dataset version', async () => {
    const version = { number: 2, goldens: [] };
    fetchMock.mockResolvedValueOnce(json(version));

    const result = await queryClient().query(
      datasetVersionQueryOptions('acme', 'support-bot', '2'),
    );

    expect(result).toEqual(version);
    const { url, init } = lastCall();
    expect(init.method).toBe('GET');
    expect(url.pathname).toBe('/api/v1/products/acme/support-bot/dataset/versions/2');
  });

  it('sends a non-numeric version to the backend unchanged', async () => {
    await queryClient().query(datasetVersionQueryOptions('acme', 'support-bot', 'abc'));

    expect(lastCall().url.pathname).toBe('/api/v1/products/acme/support-bot/dataset/versions/abc');
  });

  it('keys every query under the Dataset key and both Product IDs', () => {
    expect(datasetSummaryQueryOptions('acme', 'bot').queryKey).toEqual([
      ...DATASET_KEY,
      'acme',
      'bot',
      'summary',
    ]);
    expect(datasetVersionQueryOptions('acme', 'bot', '3').queryKey).toEqual([
      ...DATASET_KEY,
      'acme',
      'bot',
      'version',
      '3',
    ]);
  });

  it.each([
    ['summary', 'DATASET_NOT_FOUND'],
    ['version', 'DATASET_VERSION_NOT_FOUND'],
  ] as const)('turns a 404 on the %s into an ApiError with code %s', async (read, code) => {
    fetchMock.mockResolvedValueOnce(problem(404, code));
    const options =
      read === 'summary'
        ? datasetSummaryQueryOptions('acme', 'support-bot')
        : datasetVersionQueryOptions('acme', 'support-bot', '9');

    const error: unknown = await queryClient()
      .query(options as ReturnType<typeof datasetSummaryQueryOptions>)
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code, requestId: 'r-1' });
  });
});

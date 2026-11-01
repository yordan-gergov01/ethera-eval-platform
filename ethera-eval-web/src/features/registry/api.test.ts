/**
 * Unit tests for the registry's backend calls.
 *
 * Role: proves the paths, query parameters and bodies of the three registry endpoints, and that a
 *   refused replacement arrives as an ApiError with its problems intact.
 * Used by: Vitest.
 * Depends on: ./api (with lib/api/http's `api` driven through a stubbed global fetch),
 *   lib/api/errors, config/runtime-config (stubbed window config).
 * Key invariants: the replacement body is exactly {base_version, document}; both path segments are
 *   URL-encoded; the list asks for 20 per page; the reload after a 409 reads the backend even when
 *   the cache holds the Product.
 */
import { QueryClient } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  PAGE_SIZE,
  fetchCurrentProduct,
  productQueryOptions,
  productsPageQueryOptions,
  replaceManifest,
} from './api';
import { ApiError } from '@/lib/api/errors';

const BACKEND = 'http://backend:8000';

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
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

describe('registry api', () => {
  it('lists Products with limit and offset', async () => {
    const page = { items: [], total: 0, limit: PAGE_SIZE, offset: 40 };
    fetchMock.mockResolvedValueOnce(json(page));

    const result = await new QueryClient().query(productsPageQueryOptions(40));

    expect(result).toEqual(page);
    const { url, init } = lastCall();
    expect(init.method).toBe('GET');
    expect(url.origin + url.pathname).toBe(`${BACKEND}/api/v1/products`);
    expect(Object.fromEntries(url.searchParams)).toEqual({ limit: '20', offset: '40' });
  });

  it('reads one Product with URL-encoded identifiers', async () => {
    await new QueryClient().query(productQueryOptions('acme', 'a/b c'));

    const { url, init } = lastCall();
    expect(init.method).toBe('GET');
    expect(url.pathname).toBe('/api/v1/products/acme/a%2Fb%20c');
  });

  it('reloads the current Product from the backend although the cache holds an older one', async () => {
    // A cache that would never refetch on its own: only the reload's own staleTime can make it ask.
    const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
    const key = productQueryOptions('acme', 'support-bot').queryKey;
    queryClient.setQueryData(key, { client_id: 'acme', manifest: { version: 1 } } as never);
    const current = { client_id: 'acme', project_id: 'support-bot', manifest: { version: 2 } };
    fetchMock.mockResolvedValueOnce(json(current));

    const result = await fetchCurrentProduct(queryClient, 'acme', 'support-bot');

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(result).toEqual(current);
    expect(queryClient.getQueryData(key)).toEqual(current);
  });

  it('replaces the Manifest with exactly base_version and document', async () => {
    const manifest = { version: 2, document: 'x' };
    fetchMock.mockResolvedValueOnce(json(manifest, 201));

    const result = await replaceManifest('acme', 'support-bot', 1, 'product: {}\n');

    expect(result).toEqual(manifest);
    const { url, init } = lastCall();
    expect(init.method).toBe('PUT');
    expect(url.pathname).toBe('/api/v1/products/acme/support-bot/manifest');
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init.body as string)).toEqual({
      base_version: 1,
      document: 'product: {}\n',
    });
  });

  it('turns a MANIFEST_INVALID answer into an ApiError with every problem', async () => {
    const errors = [
      { field: 'bindings[0].model', message: 'Not full.', type: 'alias' },
      { field: 'gate', message: 'Unknown.', type: 'unknown_key' },
    ];
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          title: 'Unprocessable Content',
          status: 422,
          detail: 'The Manifest is invalid.',
          code: 'MANIFEST_INVALID',
          errors,
        }),
        { status: 422, headers: { 'Content-Type': 'application/problem+json' } },
      ),
    );

    const error: unknown = await replaceManifest('acme', 'support-bot', 1, 'x').catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: 'MANIFEST_INVALID', problems: errors });
  });
});

/**
 * Unit tests for the Manifest replacement hook.
 *
 * Role: proves a 201 (new version) and a 200 (equal Manifest) both write the returned Manifest
 *   into the Product's cache and invalidate the Products list pages, that the PUT carries the base
 *   version and document, and that a refusal touches neither and is not retried.
 * Used by: Vitest.
 * Depends on: ./use-replace-manifest, ./api (productQueryOptions, productsPageQueryOptions),
 *   lib/api/errors ApiError, react-dom/server renderToStaticMarkup, TanStack Query; the global
 *   fetch and window config stubbed (the backend is external).
 * Key invariants: the hook runs inside a statically rendered probe and its `mutateAsync` is
 *   called afterwards: a mutation runs without a mounted component, so the hook's real onSuccess
 *   runs against a real cache; the client is the library's default one, so "not retried" is the
 *   hook's own behaviour, not a test setting.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { productQueryOptions, productsPageQueryOptions } from './api';
import { useReplaceManifest } from './use-replace-manifest';
import { ApiError } from '@/lib/api/errors';
import type { Manifest, Product } from '@/lib/api/types';

const manifest = (version: number): Manifest => ({
  version,
  bindings: [],
  allowed_providers: ['mock'],
  document: `version ${String(version)}`,
  created_at: '2026-11-01T09:00:00+00:00',
  created_by: 'owner',
});

const PRODUCT: Product = { client_id: 'acme', project_id: 'support-bot', manifest: manifest(1) };

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  vi.stubGlobal('window', { __APP_CONFIG__: { backendUrl: 'http://backend:8000' } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** A cache holding the Product and a list page, a backend answering `response`, and the hook. */
function setup(response: Response) {
  fetchMock = vi.fn<typeof fetch>(() => Promise.resolve(response));
  vi.stubGlobal('fetch', fetchMock);
  const queryClient = new QueryClient();
  const detailKey = productQueryOptions('acme', 'support-bot').queryKey;
  const pageKey = productsPageQueryOptions(0).queryKey;
  queryClient.setQueryData(detailKey, PRODUCT);
  queryClient.setQueryData(pageKey, { items: [], total: 1, limit: 20, offset: 0 });
  let result: ReturnType<typeof useReplaceManifest> | undefined;
  function Probe() {
    result = useReplaceManifest('acme', 'support-bot');
    return null;
  }
  renderToStaticMarkup(
    createElement(QueryClientProvider, { client: queryClient }, createElement(Probe)),
  );
  if (!result) {
    throw new Error('the probe did not render');
  }
  return { queryClient, detailKey, pageKey, mutation: result };
}

const json = (body: unknown, status: number) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('useReplaceManifest', () => {
  it.each([201, 200])(
    'a %i answer writes the returned Manifest into the Product and refreshes the list',
    async (status) => {
      const { queryClient, detailKey, pageKey, mutation } = setup(json(manifest(2), status));

      await mutation.mutateAsync({ baseVersion: 1, document: 'version 2' });

      expect(queryClient.getQueryData(detailKey)).toEqual({ ...PRODUCT, manifest: manifest(2) });
      expect(queryClient.getQueryState(pageKey)?.isInvalidated).toBe(true);
      const [url, init] = fetchMock.mock.calls[0] ?? [];
      expect(url).toEqual(new URL('http://backend:8000/api/v1/products/acme/support-bot/manifest'));
      expect(init?.method).toBe('PUT');
      expect(init?.body).toBe('{"base_version":1,"document":"version 2"}');
    },
  );

  it('a refused replacement changes nothing in the cache and is not retried', async () => {
    const body = {
      title: 'Conflict',
      status: 409,
      detail: 'Stale.',
      code: 'MANIFEST_VERSION_CONFLICT',
    };
    const refusal = new Response(JSON.stringify(body), {
      status: 409,
      headers: { 'Content-Type': 'application/problem+json' },
    });
    const { queryClient, detailKey, pageKey, mutation } = setup(refusal);

    await expect(mutation.mutateAsync({ baseVersion: 1, document: 'x' })).rejects.toBeInstanceOf(
      ApiError,
    );

    expect(queryClient.getQueryData(detailKey)).toEqual(PRODUCT);
    expect(queryClient.getQueryState(pageKey)?.isInvalidated).toBe(false);
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});

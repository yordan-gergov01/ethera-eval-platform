/**
 * Queries and backend calls of the registry feature.
 *
 * Role: query options for the Products list and one Product, a fresh read of one Product, and the
 *   Manifest replacement call.
 * Used by: features/registry ProductDetail, ReplaceManifestForm, use-products-page,
 *   use-replace-manifest; api.test.ts.
 * Depends on: api from lib/api/http, TanStack Query; GET /api/v1/products,
 *   GET /api/v1/products/{client_id}/{project_id},
 *   PUT /api/v1/products/{client_id}/{project_id}/manifest.
 * Key invariants: every registry query key starts with PRODUCTS_KEY so one invalidation refreshes
 *   them all; 20 Products per page; fetchCurrentProduct always asks the backend, never the cache
 *   (the reload after a 409 must see the new current version); both path segments are
 *   URL-encoded; the replacement sends exactly `base_version` and `document` (the backend rejects
 *   unknown fields); the list keeps the previous page as placeholder while the next loads.
 */
import { keepPreviousData, queryOptions, type QueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/http';
import type { Manifest, ManifestReplace, Product, ProductPage } from '@/lib/api/types';

export const PAGE_SIZE = 20;

/** Every cached registry query starts with this key, so one invalidation refreshes them all. */
export const PRODUCTS_KEY = ['products'] as const;

/** The path of one Product, with both identifiers URL-encoded. */
export function productPath(clientId: string, projectId: string) {
  return `/api/v1/products/${encodeURIComponent(clientId)}/${encodeURIComponent(projectId)}`;
}

export const productsPageQueryOptions = (offset: number) =>
  queryOptions({
    queryKey: [...PRODUCTS_KEY, 'page', offset],
    queryFn: ({ signal }) =>
      api.get<ProductPage>('/api/v1/products', { query: { limit: PAGE_SIZE, offset }, signal }),
    // Keep showing the current page while the next one loads.
    placeholderData: keepPreviousData,
  });

export const productQueryOptions = (clientId: string, projectId: string) =>
  queryOptions({
    queryKey: [...PRODUCTS_KEY, 'detail', clientId, projectId],
    queryFn: ({ signal }) => api.get<Product>(productPath(clientId, projectId), { signal }),
  });

/**
 * Reads one Product from the backend even when the cache holds it, and stores
 * the answer in the cache.
 */
export function fetchCurrentProduct(queryClient: QueryClient, clientId: string, projectId: string) {
  return queryClient.query({ ...productQueryOptions(clientId, projectId), staleTime: 0 });
}

/**
 * Replaces a Product's Manifest. `baseVersion` is the version the caller is
 * replacing; the backend answers 409 when it is no longer current.
 */
export function replaceManifest(
  clientId: string,
  projectId: string,
  baseVersion: number,
  document: string,
) {
  return api.put<Manifest>(`${productPath(clientId, projectId)}/manifest`, {
    json: { base_version: baseVersion, document } satisfies ManifestReplace,
  });
}

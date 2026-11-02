/**
 * Queries of the evaluation feature.
 *
 * Role: query options for a Product's Dataset summary and for one Dataset version.
 * Used by: features/evaluation DatasetSummary and DatasetVersion; api.test.ts.
 * Depends on: api from lib/api/http, TanStack Query;
 *   GET /api/v1/products/{client_id}/{project_id}/dataset,
 *   GET /api/v1/products/{client_id}/{project_id}/dataset/versions/{number}.
 * Key invariants: every evaluation query key starts with DATASET_KEY and both Product IDs; every
 *   path segment is URL-encoded, the version too: it is passed as the URL gave it, so a
 *   non-numeric `?version=` reaches the backend, which answers DATASET_VERSION_NOT_FOUND
 *   (contract C-205) and stays the one judge of what a version is; read-only, no mutations.
 */
import { queryOptions } from '@tanstack/react-query';

import { api } from '@/lib/api/http';
import type { DatasetSummary, DatasetVersion } from '@/lib/api/types';

/** Every cached evaluation query starts with this key. */
export const DATASET_KEY = ['dataset'] as const;

/** The backend path of a Product's Dataset summary, with both identifiers URL-encoded. */
export function datasetPath(clientId: string, projectId: string): string {
  return `/api/v1/products/${encodeURIComponent(clientId)}/${encodeURIComponent(projectId)}/dataset`;
}

/** The backend path of one Dataset version; the version segment is URL-encoded as given. */
export function datasetVersionPath(clientId: string, projectId: string, version: string): string {
  return `${datasetPath(clientId, projectId)}/versions/${encodeURIComponent(version)}`;
}

export const datasetSummaryQueryOptions = (clientId: string, projectId: string) =>
  queryOptions({
    queryKey: [...DATASET_KEY, clientId, projectId, 'summary'],
    queryFn: ({ signal }) => api.get<DatasetSummary>(datasetPath(clientId, projectId), { signal }),
  });

export const datasetVersionQueryOptions = (clientId: string, projectId: string, version: string) =>
  queryOptions({
    queryKey: [...DATASET_KEY, clientId, projectId, 'version', version],
    queryFn: ({ signal }) =>
      api.get<DatasetVersion>(datasetVersionPath(clientId, projectId, version), { signal }),
  });

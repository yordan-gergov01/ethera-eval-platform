/**
 * Mutation hook that replaces one Product's Manifest.
 *
 * Role: PUTs the new eval.yaml text, stores the answer in the Product's cache and refreshes the
 *   Products list pages.
 * Used by: features/registry/ReplaceManifestForm.tsx.
 * Depends on: ./api replaceManifest, productQueryOptions and PRODUCTS_KEY; TanStack Query.
 * Key invariants: a 201 (new version) and a 200 (equal Manifest, nothing changed) are both
 *   successes and both write the returned Manifest into the Product's cache; the list pages are
 *   invalidated because their version and last-change columns may have moved; never retried
 *   (mutations default to no retry).
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { PRODUCTS_KEY, productQueryOptions, replaceManifest } from './api';

export interface ManifestReplacement {
  baseVersion: number;
  document: string;
}

/** Replaces the Manifest and refreshes what shows it. */
export function useReplaceManifest(clientId: string, projectId: string) {
  const queryClient = useQueryClient();
  const detailKey = productQueryOptions(clientId, projectId).queryKey;
  return useMutation({
    mutationFn: ({ baseVersion, document }: ManifestReplacement) =>
      replaceManifest(clientId, projectId, baseVersion, document),
    onSuccess: async (manifest) => {
      queryClient.setQueryData(detailKey, (product) =>
        product ? { ...product, manifest } : product,
      );
      await queryClient.invalidateQueries({ queryKey: [...PRODUCTS_KEY, 'page'] });
    },
  });
}

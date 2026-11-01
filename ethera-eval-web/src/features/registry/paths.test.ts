/**
 * Unit tests for the registry's browser paths.
 *
 * Role: proves the Product and Replace Manifest page paths.
 * Used by: Vitest.
 * Depends on: ./paths.
 * Key invariants: identifiers are URL-encoded, so no identifier can change the route.
 */
import { describe, expect, it } from 'vitest';

import { productPagePath, replaceManifestPagePath } from './paths';

describe('registry paths', () => {
  it('builds the Product page path', () => {
    expect(productPagePath('acme', 'support-bot')).toBe('/products/acme/support-bot');
  });

  it('builds the Replace Manifest page path', () => {
    expect(replaceManifestPagePath('acme', 'support-bot')).toBe(
      '/products/acme/support-bot/manifest',
    );
  });

  it('encodes identifiers', () => {
    expect(productPagePath('a/b', 'c d')).toBe('/products/a%2Fb/c%20d');
  });
});

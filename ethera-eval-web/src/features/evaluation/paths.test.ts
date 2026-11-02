/**
 * Unit tests for the evaluation feature's browser paths.
 *
 * Role: proves the Dataset page path, with and without a version.
 * Used by: Vitest.
 * Depends on: ./paths.
 * Key invariants: identifiers are URL-encoded, so no identifier can change the route.
 */
import { describe, expect, it } from 'vitest';

import { datasetPagePath } from './paths';

describe('evaluation paths', () => {
  it('builds the Dataset page path of the current version', () => {
    expect(datasetPagePath('acme', 'support-bot')).toBe('/products/acme/support-bot/dataset');
  });

  it('builds the Dataset page path of one version', () => {
    expect(datasetPagePath('acme', 'support-bot', 2)).toBe(
      '/products/acme/support-bot/dataset?version=2',
    );
  });

  it('encodes identifiers', () => {
    expect(datasetPagePath('a/b', 'c?d')).toBe('/products/a%2Fb/c%3Fd/dataset');
  });
});

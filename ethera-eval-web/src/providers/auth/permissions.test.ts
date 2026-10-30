/**
 * Unit tests for the permission check.
 *
 * Role: proves hasPermission for listed, unlisted and unknown permissions.
 * Used by: Vitest.
 * Depends on: ./permissions.
 * Key invariants: pins "is false while the permissions are unknown".
 */
import { describe, expect, it } from 'vitest';

import { hasPermission } from './permissions';

describe('hasPermission', () => {
  it('is true for a listed permission', () => {
    expect(hasPermission(['users:create', 'users:read'], 'users:read')).toBe(true);
  });

  it('is false for a permission that is not listed', () => {
    expect(hasPermission(['users:create', 'users:update'], 'users:read')).toBe(false);
  });

  it('is false while the permissions are unknown', () => {
    expect(hasPermission(undefined, 'users:read')).toBe(false);
    expect(hasPermission([], 'users:read')).toBe(false);
  });
});

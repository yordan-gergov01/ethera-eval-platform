/**
 * Unit tests for the user role label map.
 *
 * Role: proves every built-in role has a label and unknown names are shown raw.
 * Used by: Vitest.
 * Depends on: ./labels, RoleName from lib/api/types.
 * Key invariants: the role list below is typed against the generated RoleName, so the type check
 *   fails when the backend adds a role this test (and the map) does not name.
 */
import { describe, expect, it } from 'vitest';

import { ROLE_LABELS, roleLabel } from './labels';
import type { RoleName } from '@/lib/api/types';

// A Record over RoleName: adding a role to the generated enum makes this object incomplete.
const EVERY_ROLE: Record<RoleName, true> = { admin: true, user: true };

describe('ROLE_LABELS', () => {
  it('labels every role and nothing else', () => {
    expect(Object.keys(ROLE_LABELS).sort()).toEqual(Object.keys(EVERY_ROLE).sort());
  });

  it('renders the built-in roles in English', () => {
    expect(roleLabel('admin')).toBe('Administrator');
    expect(roleLabel('user')).toBe('User');
  });

  it('shows an unknown role name raw', () => {
    expect(roleLabel('auditor')).toBe('auditor');
    expect(roleLabel('constructor')).toBe('constructor');
  });
});

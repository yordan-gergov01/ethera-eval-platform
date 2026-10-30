/**
 * Unit tests for changedFields.
 *
 * Role: proves only changed fields are returned.
 * Used by: Vitest.
 * Depends on: ./changed-fields.
 * Key invariants: pins that nothing changed gives an empty object, which forms read as nothing to
 *   save.
 */
import { describe, expect, it } from 'vitest';

import { changedFields } from './changed-fields';

describe('changedFields', () => {
  const initial = { full_name: 'Alice', email: 'alice@example.com', is_active: true };

  it('returns only the fields that changed', () => {
    expect(
      changedFields(initial, { ...initial, email: 'a@example.com', is_active: false }),
    ).toEqual({ email: 'a@example.com', is_active: false });
  });

  it('returns an empty object when nothing changed', () => {
    expect(changedFields(initial, { ...initial })).toEqual({});
  });
});

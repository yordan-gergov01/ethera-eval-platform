/**
 * Unit tests for the registry's label maps.
 *
 * Role: proves every role, provider and problem type has a non-empty English label that differs
 *   from the raw value, that the accepted labels are used, and that unknown values are shown raw.
 * Used by: Vitest.
 * Depends on: ./labels.
 * Key invariants: completeness of the role and provider maps is the type check's job (they are
 *   keyed on the generated unions), so nothing here restates those value sets; the problem types
 *   are pinned to contract §3.3 here because no generated type carries them.
 */
import { describe, expect, it } from 'vitest';

import {
  BINDING_ROLE_LABELS,
  PROBLEM_TYPES,
  PROBLEM_TYPE_LABELS,
  PROVIDER_LABELS,
  labelOf,
} from './labels';

const MAPS: [string, Readonly<Record<string, string>>][] = [
  ['binding roles', BINDING_ROLE_LABELS],
  ['providers', PROVIDER_LABELS],
  ['problem types', PROBLEM_TYPE_LABELS],
];

describe('registry label maps', () => {
  it.each(MAPS)('gives every one of the %s a readable label', (_, labels) => {
    for (const [value, label] of Object.entries(labels)) {
      expect(label.trim()).not.toBe('');
      expect(label).not.toBe(value);
    }
  });

  it('labels exactly the problem types of the contract', () => {
    expect(Object.keys(PROBLEM_TYPE_LABELS).sort()).toEqual([...PROBLEM_TYPES].sort());
    expect([...PROBLEM_TYPES].sort()).toEqual(
      [
        'malformed',
        'unsupported_syntax',
        'duplicate_key',
        'unknown_key',
        'missing',
        'wrong_type',
        'invalid_value',
        'product_mismatch',
        'unknown_provider',
        'alias',
        'provider_not_allowed',
        'duplicate_role',
        'generation_required',
        'duplicate_value',
      ].sort(),
    );
  });

  it('uses the labels the owner accepted (PP-011)', () => {
    expect(BINDING_ROLE_LABELS).toEqual({
      generation: 'Generation',
      judge: 'Judge',
      embedding: 'Embedding',
    });
    expect(PROVIDER_LABELS).toEqual({ mock: 'Mock provider' });
  });

  it('shows an unknown value raw, including inherited property names', () => {
    expect(labelOf(PROVIDER_LABELS, 'other')).toBe('other');
    expect(labelOf(PROVIDER_LABELS, 'toString')).toBe('toString');
  });
});

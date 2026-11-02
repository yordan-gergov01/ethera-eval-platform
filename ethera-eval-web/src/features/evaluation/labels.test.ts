/**
 * Unit tests for the evaluation feature's label maps.
 *
 * Role: proves every Decision, failure type and Golden owner has the English label the owner
 *   accepted, that the failure types keep their display order, that unknown values are shown raw,
 *   and that a map missing a value is a type error.
 * Used by: Vitest (runtime cases) and `tsc -b` (the @ts-expect-error negative case).
 * Depends on: ./labels, the generated unions from lib/api/types.
 * Key invariants: completeness is the type check's job (the maps are keyed on the generated
 *   unions); the negative case proves that gate fires: if a map missing a key ever stopped being
 *   a type error, the unused @ts-expect-error would fail `tsc -b`.
 */
import { describe, expect, it } from 'vitest';

import {
  DECISION_LABELS,
  FAILURE_TYPES,
  FAILURE_TYPE_LABELS,
  GOLDEN_OWNER_LABELS,
  goldenCount,
  labelOf,
} from './labels';
import type { Decision } from '@/lib/api/types';

describe('evaluation label maps', () => {
  it('uses the Decision labels the owner accepted (PP-202)', () => {
    expect(DECISION_LABELS).toEqual({
      approve_return: 'Approve return',
      deny_return: 'Deny return',
      explain_return: 'Explain return',
      approve_refund: 'Approve refund',
      deny_refund: 'Deny refund',
      report_status: 'Report status',
      answer_from_docs: 'Answer from documents',
      escalate: 'Escalate',
    });
  });

  it('uses the failure-type labels the owner accepted (PP-203), in display order', () => {
    expect(FAILURE_TYPE_LABELS).toEqual({
      date_math: 'Date math',
      refund_rules: 'Refund rules',
      invented_facts: 'Invented facts',
      out_of_docs: 'Out of documents',
      retrieval_miss: 'Retrieval miss',
      order_status_tool: 'Order status (tool)',
    });
    expect(FAILURE_TYPES).toEqual([
      'date_math',
      'refund_rules',
      'invented_facts',
      'out_of_docs',
      'retrieval_miss',
      'order_status_tool',
    ]);
  });

  it('uses the owner labels the owner accepted (PP-205)', () => {
    expect(GOLDEN_OWNER_LABELS).toEqual({
      engineering: 'Engineering',
      support_content: 'Support content',
    });
  });

  it('counts Goldens in singular and plural', () => {
    expect(goldenCount(1)).toBe('1 Golden');
    expect(goldenCount(0)).toBe('0 Goldens');
    expect(goldenCount(19)).toBe('19 Goldens');
  });

  it('shows an unknown value raw, including inherited property names', () => {
    expect(labelOf(DECISION_LABELS, 'refund_partially')).toBe('refund_partially');
    expect(labelOf(GOLDEN_OWNER_LABELS, 'toString')).toBe('toString');
    expect(labelOf(DECISION_LABELS, 'escalate')).toBe('Escalate');
  });

  it('refuses a label map that misses a value at type-check time', () => {
    // @ts-expect-error a Record<Decision, string> without `escalate` must not type-check.
    const incomplete: Record<Decision, string> = {
      approve_return: 'Approve return',
      deny_return: 'Deny return',
      explain_return: 'Explain return',
      approve_refund: 'Approve refund',
      deny_refund: 'Deny refund',
      report_status: 'Report status',
      answer_from_docs: 'Answer from documents',
    };
    expect(Object.keys(incomplete)).toHaveLength(7);
  });
});

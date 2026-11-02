/**
 * Label maps for the evaluation feature's machine values.
 *
 * Role: English labels for Decisions, failure types and Golden owners (D-012, PP-202, PP-203,
 *   PP-205), the fixed display order of the failure types, and the Golden count text.
 * Used by: features/evaluation DatasetSummary and DatasetVersion; labels.test.ts.
 * Depends on: the Decision, FailureType and GoldenOwner types from lib/api/types (generated from
 *   the evaluation module's response enums).
 * Key invariants: every map is typed `Record<Value, Label>` on a generated union, so a value the
 *   backend adds without a label fails the type check; FAILURE_TYPES is the keys of its label map,
 *   so the summary always shows all six types, zeros included, in one order; a value the map does
 *   not know is shown raw (never hidden) so a newer backend stays readable; labels are plain text.
 */
import type { Decision, FailureType, GoldenOwner } from '@/lib/api/types';

/** The Decision value set (PP-202). */
export const DECISION_LABELS: Record<Decision, string> = {
  approve_return: 'Approve return',
  deny_return: 'Deny return',
  explain_return: 'Explain return',
  approve_refund: 'Approve refund',
  deny_refund: 'Deny refund',
  report_status: 'Report status',
  answer_from_docs: 'Answer from documents',
  escalate: 'Escalate',
};

/** The failure-type value set (PP-203). */
export const FAILURE_TYPE_LABELS: Record<FailureType, string> = {
  date_math: 'Date math',
  refund_rules: 'Refund rules',
  invented_facts: 'Invented facts',
  out_of_docs: 'Out of documents',
  retrieval_miss: 'Retrieval miss',
  order_status_tool: 'Order status (tool)',
};

/** The failure types in display order: the keys of their label map. */
export const FAILURE_TYPES = Object.keys(FAILURE_TYPE_LABELS) as FailureType[];

/** The teams that can own a Golden (PP-205). */
export const GOLDEN_OWNER_LABELS: Record<GoldenOwner, string> = {
  engineering: 'Engineering',
  support_content: 'Support content',
};

/** "1 Golden", "19 Goldens". */
export function goldenCount(count: number): string {
  return `${String(count)} ${count === 1 ? 'Golden' : 'Goldens'}`;
}

/** The label of a value, or the value itself when the map does not know it. */
export function labelOf(labels: Readonly<Record<string, string>>, value: string): string {
  return Object.hasOwn(labels, value) ? (labels[value] ?? value) : value;
}

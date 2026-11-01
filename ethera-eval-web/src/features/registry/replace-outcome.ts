/**
 * What the Replace Manifest form shows after a refused replacement.
 *
 * Role: turns the error of a failed PUT .../manifest into one outcome the form renders.
 * Used by: features/registry/ReplaceManifestForm.tsx, replace-outcome.test.ts.
 * Depends on: ApiError (its code and problems list) from lib/api/errors, ./labels.
 * Key invariants: branches on `code`, never on `detail`; only MANIFEST_INVALID problems go through
 *   the problem-type label map, every problem kept (several on one field are all shown) in the
 *   backend's order; a VALIDATION_FAILED 422 (empty or overlong document) is a document error,
 *   not a Manifest problem; 409 MANIFEST_VERSION_CONFLICT and 404 PRODUCT_NOT_FOUND get their own
 *   outcomes; anything else stays a general error. Messages come from the API and are rendered
 *   as plain text.
 */
import { PROBLEM_TYPE_LABELS, labelOf } from './labels';
import { ApiError } from '@/lib/api/errors';

/** One Manifest problem as shown: its field path, its type and type label, the API's message. */
export interface ProblemLine {
  field: string;
  type: string;
  typeLabel: string;
  message: string;
}

export type ReplaceOutcome =
  | { kind: 'invalid'; problems: ProblemLine[] }
  | { kind: 'document'; message: string }
  | { kind: 'conflict' }
  | { kind: 'not-found' }
  | { kind: 'other'; error: unknown };

/** Classifies the error of a refused replacement. */
export function replaceOutcome(error: unknown): ReplaceOutcome {
  if (!(error instanceof ApiError)) {
    return { kind: 'other', error };
  }
  switch (error.code) {
    case 'MANIFEST_INVALID':
      return {
        kind: 'invalid',
        problems: error.problems.map(({ field, type, message }) => ({
          field,
          type,
          typeLabel: labelOf(PROBLEM_TYPE_LABELS, type),
          message,
        })),
      };
    case 'VALIDATION_FAILED': {
      const document = error.problems.find(({ field }) => field === 'body.document');
      return document ? { kind: 'document', message: document.message } : { kind: 'other', error };
    }
    case 'MANIFEST_VERSION_CONFLICT':
      return { kind: 'conflict' };
    case 'PRODUCT_NOT_FOUND':
      return { kind: 'not-found' };
    default:
      return { kind: 'other', error };
  }
}

/**
 * Unit tests for what the Replace Manifest form shows after a refusal.
 *
 * Role: proves the 422 MANIFEST_INVALID, 422 VALIDATION_FAILED, 409, 404 and other branches of
 *   replaceOutcome.
 * Used by: Vitest.
 * Depends on: ./replace-outcome, ApiError and NetworkError from lib/api/errors.
 * Key invariants: every problem survives, two on one field included, in the API's order and with
 *   the full field path; the problem type is labelled, an unknown type shown raw; the decision is
 *   by code, never by detail. The form component itself is not rendered (Vitest runs in node with
 *   no DOM library), so this pure function carries the form's branching.
 */
import { describe, expect, it } from 'vitest';

import { replaceOutcome } from './replace-outcome';
import { ApiError, NetworkError } from '@/lib/api/errors';

function apiError(status: number, code: string, problems: { field: string; type: string }[] = []) {
  return new ApiError({
    status,
    code,
    title: 'Error',
    detail: 'Refused.',
    problems: problems.map((problem) => ({ ...problem, message: `Message for ${problem.type}.` })),
  });
}

describe('replaceOutcome', () => {
  it('lists every MANIFEST_INVALID problem by field with its type label and message', () => {
    const outcome = replaceOutcome(
      apiError(422, 'MANIFEST_INVALID', [
        { field: 'bindings[0].model', type: 'alias' },
        { field: 'bindings[1].provider', type: 'unknown_provider' },
        { field: 'bindings[1].provider', type: 'provider_not_allowed' },
        { field: 'gate', type: 'unknown_key' },
      ]),
    );

    expect(outcome).toEqual({
      kind: 'invalid',
      problems: [
        {
          field: 'bindings[0].model',
          type: 'alias',
          typeLabel: 'Not a full model ID',
          message: 'Message for alias.',
        },
        {
          field: 'bindings[1].provider',
          type: 'unknown_provider',
          typeLabel: 'Unknown provider',
          message: 'Message for unknown_provider.',
        },
        {
          field: 'bindings[1].provider',
          type: 'provider_not_allowed',
          typeLabel: 'Provider not allowed',
          message: 'Message for provider_not_allowed.',
        },
        {
          field: 'gate',
          type: 'unknown_key',
          typeLabel: 'Unknown key',
          message: 'Message for unknown_key.',
        },
      ],
    });
  });

  it('shows an unknown problem type raw', () => {
    const outcome = replaceOutcome(
      apiError(422, 'MANIFEST_INVALID', [{ field: 'document', type: 'brand_new' }]),
    );

    expect(outcome).toMatchObject({ kind: 'invalid', problems: [{ typeLabel: 'brand_new' }] });
  });

  it('puts a VALIDATION_FAILED on the document field, not in the problem list', () => {
    const outcome = replaceOutcome(
      apiError(422, 'VALIDATION_FAILED', [{ field: 'body.document', type: 'string_too_long' }]),
    );

    expect(outcome).toEqual({ kind: 'document', message: 'Message for string_too_long.' });
  });

  it('keeps a VALIDATION_FAILED on another field as a general error', () => {
    const error = apiError(422, 'VALIDATION_FAILED', [
      { field: 'body.base_version', type: 'greater_than_equal' },
    ]);

    expect(replaceOutcome(error)).toEqual({ kind: 'other', error });
  });

  it('reports a version conflict as a conflict', () => {
    expect(replaceOutcome(apiError(409, 'MANIFEST_VERSION_CONFLICT'))).toEqual({
      kind: 'conflict',
    });
  });

  it('reports PRODUCT_NOT_FOUND as not found', () => {
    expect(replaceOutcome(apiError(404, 'PRODUCT_NOT_FOUND'))).toEqual({ kind: 'not-found' });
  });

  it('keeps any other error general', () => {
    const forbidden = apiError(403, 'PERMISSION_DENIED');
    const network = new NetworkError(new Error('down'));

    expect(replaceOutcome(forbidden)).toEqual({ kind: 'other', error: forbidden });
    expect(replaceOutcome(network)).toEqual({ kind: 'other', error: network });
  });
});

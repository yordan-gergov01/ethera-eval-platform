/**
 * Unit tests for splitting a failed submission into field and general errors.
 *
 * Role: proves toFormErrors.
 * Used by: Vitest.
 * Depends on: ./errors, ./form-errors.
 * Key invariants: pins that the same code maps to different fields in different forms and that
 *   errors which are not API errors stay general.
 */
import { describe, expect, it } from 'vitest';

import { ApiError, NetworkError } from './errors';
import { toFormErrors } from './form-errors';

function apiError(code: string, fieldErrors: Record<string, string> = {}, status = 422) {
  return new ApiError({ status, code, title: 'Error', detail: `detail of ${code}`, fieldErrors });
}

const FIELDS = ['username', 'email', 'password'] as const;

describe('toFormErrors', () => {
  it('puts validation errors on their fields', () => {
    const error = apiError('VALIDATION_FAILED', { username: 'Too short', email: 'Invalid' });

    expect(toFormErrors(error, FIELDS)).toEqual({
      fields: { username: 'Too short', email: 'Invalid' },
      general: null,
    });
  });

  it('keeps the error general when a validation error has no field in the form', () => {
    const error = apiError('VALIDATION_FAILED', { username: 'Too short', limit: 'Too large' });

    expect(toFormErrors(error, FIELDS)).toEqual({
      fields: { username: 'Too short' },
      general: error,
    });
  });

  it('puts a code on the field this form maps it to', () => {
    const error = apiError('USERNAME_TAKEN', {}, 409);

    expect(toFormErrors(error, FIELDS, { USERNAME_TAKEN: 'username' })).toEqual({
      fields: { username: 'detail of USERNAME_TAKEN' },
      general: null,
    });
  });

  it('maps the same code to different fields in different forms', () => {
    const error = apiError('WEAK_PASSWORD');

    expect(
      toFormErrors(error, ['current_password', 'new_password'], { WEAK_PASSWORD: 'new_password' })
        .fields,
    ).toEqual({ new_password: 'detail of WEAK_PASSWORD' });
  });

  it('keeps other API errors general', () => {
    const error = apiError('LAST_ADMIN_PROTECTED', {}, 409);
    expect(toFormErrors(error, FIELDS, { USERNAME_TAKEN: 'username' })).toEqual({
      fields: {},
      general: error,
    });
  });

  it('keeps errors that are not API errors general', () => {
    const error = new NetworkError(new TypeError('Failed to fetch'));
    expect(toFormErrors(error, FIELDS)).toEqual({ fields: {}, general: error });
  });
});

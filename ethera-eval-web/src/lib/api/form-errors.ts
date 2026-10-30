/**
 * Splits a failed form submission into field errors and a general error.
 *
 * Role: lets every form place backend errors next to its fields.
 * Used by: features PasswordForm, ProfileForm, CreateUserForm, EditUserForm; form-errors.test.ts.
 * Depends on: ApiError from ./errors, ErrorCode from ./types.
 * Key invariants: codes map to fields per form through `codeFields`, because the same code belongs
 *   to different fields in different forms; `general` is null only when every error found a field
 *   in this form; anything that is not an ApiError stays general.
 */
import { ApiError } from './errors';
import type { ErrorCode } from './types';

export interface FormErrors<F extends string> {
  /** Messages to show next to the form's fields. */
  fields: Partial<Record<F, string>>;
  /** An error that belongs to no field, shown above the form; null when every error has a field. */
  general: unknown;
}

/**
 * Splits a failed submission into field errors and a general error. Field
 * errors come from a 422's `errors` list and from codes that name a field in
 * this form, such as USERNAME_TAKEN; `codeFields` maps those codes to fields
 * because the same code belongs to different fields in different forms.
 */
export function toFormErrors<F extends string>(
  error: unknown,
  fields: readonly F[],
  codeFields: Partial<Record<ErrorCode, F>> = {},
): FormErrors<F> {
  if (!(error instanceof ApiError)) {
    return { fields: {}, general: error };
  }

  const result: Partial<Record<F, string>> = {};
  let unmatched = false;
  for (const [name, message] of Object.entries(error.fieldErrors)) {
    if ((fields as readonly string[]).includes(name)) {
      result[name as F] = message;
    } else {
      unmatched = true;
    }
  }

  const codeField = codeFields[error.code as ErrorCode];
  if (codeField) {
    result[codeField] = error.detail;
  }

  const matched = Object.keys(result).length > 0;
  return { fields: result, general: matched && !unmatched ? null : error };
}

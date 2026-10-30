/**
 * Change-password form with client checks and server error mapping.
 *
 * Role: lets the signed-in user change their own password.
 * Used by: pages/ProfilePage.tsx.
 * Depends on: ./use-change-password, ErrorMessage, Field, toFormErrors (lib/api/form-errors),
 *   validatePassword (utils/validation).
 * Key invariants: success ends the local session, because the backend ends every session of the
 *   user, and the user logs in again with the new password (template_web D-003);
 *   INVALID_CURRENT_PASSWORD and WEAK_PASSWORD are shown on their fields; client checks only save a
 *   round trip, the backend decides.
 */
import { useState, type SubmitEvent } from 'react';

import { useChangePassword } from './use-change-password';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Field } from '@/components/ui/Field';
import { toFormErrors } from '@/lib/api/form-errors';
import { validatePassword } from '@/utils/validation';

const FIELDS = ['current_password', 'new_password', 'confirm_password'] as const;
type PasswordField = (typeof FIELDS)[number];

/**
 * Changing the password ends every session of the user on the backend, so the
 * local session ends too and the user logs in again with the new password.
 */
export function PasswordForm() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [clientErrors, setClientErrors] = useState<Partial<Record<PasswordField, string>>>({});

  const mutation = useChangePassword();

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    mutation.reset();

    const errors: Partial<Record<PasswordField, string>> = {
      current_password: currentPassword === '' ? 'Enter your current password.' : undefined,
      new_password: validatePassword(newPassword),
      confirm_password: confirmPassword === newPassword ? undefined : 'The passwords do not match.',
    };
    setClientErrors(errors);
    if (Object.values(errors).some(Boolean)) {
      return;
    }
    mutation.mutate({ current_password: currentPassword, new_password: newPassword });
  };

  const server = mutation.error
    ? toFormErrors(mutation.error, FIELDS, {
        INVALID_CURRENT_PASSWORD: 'current_password',
        WEAK_PASSWORD: 'new_password',
      })
    : { fields: {}, general: null };
  const fieldError = (field: PasswordField) => clientErrors[field] ?? server.fields[field];

  return (
    <form onSubmit={submit} noValidate>
      {server.general !== null && <ErrorMessage error={server.general} />}

      <Field label="Current password" error={fieldError('current_password')}>
        {(props) => (
          <input
            {...props}
            name="current_password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => {
              setCurrentPassword(event.target.value);
            }}
          />
        )}
      </Field>
      <Field
        label="New password"
        error={fieldError('new_password')}
        hint="12 to 128 characters, not a commonly used password, not your username or email."
      >
        {(props) => (
          <input
            {...props}
            name="new_password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => {
              setNewPassword(event.target.value);
            }}
          />
        )}
      </Field>
      <Field label="Repeat the new password" error={fieldError('confirm_password')}>
        {(props) => (
          <input
            {...props}
            name="confirm_password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => {
              setConfirmPassword(event.target.value);
            }}
          />
        )}
      </Field>
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Changing…' : 'Change password'}
      </button>
    </form>
  );
}

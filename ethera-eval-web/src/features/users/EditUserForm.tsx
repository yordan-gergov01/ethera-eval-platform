/**
 * Edit form for one user's name, email, role and active status.
 *
 * Role: admin editing of a user record; read-only without users:update.
 * Used by: features/users/UserDetail.tsx.
 * Depends on: ./api rolesQueryOptions, ./use-update-user, useAuth (user, can), changedFields,
 *   utils/validation, toFormErrors, ErrorMessage, Field.
 * Key invariants: the whole fieldset is disabled without users:update; users cannot change their
 *   own role or active status (the backend refuses it too, the controls only make it visible); only
 *   changed fields are sent and an unchanged form shows "saved" without a request.
 */
import { useQuery } from '@tanstack/react-query';
import { useState, type SubmitEvent } from 'react';

import { rolesQueryOptions } from './api';
import { useUpdateUser } from './use-update-user';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Field } from '@/components/ui/Field';
import { toFormErrors } from '@/lib/api/form-errors';
import type { RoleName, User } from '@/lib/api/types';
import { useAuth } from '@/providers/auth/auth-context';
import { changedFields } from '@/utils/changed-fields';
import { validateEmail, validateFullName } from '@/utils/validation';

const FIELDS = ['full_name', 'email', 'role', 'is_active'] as const;
type EditField = (typeof FIELDS)[number];

export interface EditUserFormProps {
  user: User;
}

/** The edit form for one user; read-only without users:update. */
export function EditUserForm({ user }: EditUserFormProps) {
  const { user: me, can } = useAuth();
  const roles = useQuery(rolesQueryOptions);
  const [fullName, setFullName] = useState(user.full_name);
  const [email, setEmail] = useState(user.email);
  const [role, setRole] = useState(user.role);
  const [isActive, setIsActive] = useState(user.is_active);
  const [clientErrors, setClientErrors] = useState<Partial<Record<EditField, string>>>({});
  const [saved, setSaved] = useState(false);

  const canEdit = can('users:update');
  // The backend refuses this too; the controls only make it visible.
  const isSelf = me?.id === user.id;
  const mutation = useUpdateUser(user.id, isSelf);

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaved(false);
    mutation.reset();

    const errors: Partial<Record<EditField, string>> = {
      full_name: validateFullName(fullName),
      email: validateEmail(email),
    };
    setClientErrors(errors);
    if (Object.values(errors).some(Boolean)) {
      return;
    }

    const changes = changedFields(
      {
        full_name: user.full_name,
        email: user.email,
        role: user.role as RoleName,
        is_active: user.is_active,
      },
      {
        full_name: fullName.trim(),
        email: email.trim(),
        role: role as RoleName,
        is_active: isActive,
      },
    );
    if (Object.keys(changes).length === 0) {
      setSaved(true);
      return;
    }
    mutation.mutate(changes, {
      onSuccess: () => {
        setSaved(true);
      },
    });
  };

  const server = mutation.error
    ? toFormErrors(mutation.error, FIELDS, { EMAIL_TAKEN: 'email' })
    : { fields: {}, general: null };
  const fieldError = (field: EditField) => clientErrors[field] ?? server.fields[field];
  const selfHint = isSelf ? 'You cannot change your own role or active status.' : undefined;

  return (
    <form onSubmit={submit} noValidate>
      {server.general !== null && <ErrorMessage error={server.general} />}
      {saved && (
        <p role="status" className="notice">
          The user is saved.
        </p>
      )}

      <fieldset disabled={!canEdit || mutation.isPending}>
        <Field label="Full name" error={fieldError('full_name')}>
          {(props) => (
            <input
              {...props}
              name="full_name"
              autoComplete="off"
              value={fullName}
              onChange={(event) => {
                setFullName(event.target.value);
              }}
            />
          )}
        </Field>
        <Field label="Email" error={fieldError('email')}>
          {(props) => (
            <input
              {...props}
              name="email"
              type="email"
              autoComplete="off"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
              }}
            />
          )}
        </Field>
        <Field label="Role" error={fieldError('role')} hint={selfHint}>
          {(props) => (
            <select
              {...props}
              name="role"
              value={role}
              disabled={isSelf}
              onChange={(event) => {
                setRole(event.target.value);
              }}
            >
              {(roles.data ?? [{ name: role }]).map(({ name }) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Status" error={fieldError('is_active')} hint={selfHint}>
          {(props) => (
            <select
              {...props}
              name="is_active"
              value={isActive ? 'active' : 'inactive'}
              disabled={isSelf}
              onChange={(event) => {
                setIsActive(event.target.value === 'active');
              }}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive (cannot log in)</option>
            </select>
          )}
        </Field>
        {canEdit && (
          <button type="submit">{mutation.isPending ? 'Saving…' : 'Save changes'}</button>
        )}
      </fieldset>
    </form>
  );
}

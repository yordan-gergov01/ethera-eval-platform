/**
 * Admin form that creates a user.
 *
 * Role: collects username, full name, email, password and role, posts them, then opens the new
 *   user's page.
 * Used by: pages/NewUserPage.tsx.
 * Depends on: ./api rolesQueryOptions, ./use-create-user, ErrorMessage, Field, toFormErrors,
 *   utils/validation, react-router useNavigate.
 * Key invariants: the role defaults to 'user' and the options come from GET /api/v1/roles;
 *   USERNAME_TAKEN, EMAIL_TAKEN and WEAK_PASSWORD are shown on their fields; text fields are
 *   trimmed, the password is sent as typed; client checks only save a round trip.
 */
import { useQuery } from '@tanstack/react-query';
import { useState, type SubmitEvent } from 'react';
import { useNavigate } from 'react-router';

import { rolesQueryOptions } from './api';
import { useCreateUser } from './use-create-user';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Field } from '@/components/ui/Field';
import { toFormErrors } from '@/lib/api/form-errors';
import type { RoleName } from '@/lib/api/types';
import {
  validateEmail,
  validateFullName,
  validatePassword,
  validateUsername,
} from '@/utils/validation';

const FIELDS = ['username', 'email', 'full_name', 'password', 'role'] as const;
type CreateField = (typeof FIELDS)[number];

export function CreateUserForm() {
  const navigate = useNavigate();
  const roles = useQuery(rolesQueryOptions);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<RoleName>('user');
  const [clientErrors, setClientErrors] = useState<Partial<Record<CreateField, string>>>({});

  const mutation = useCreateUser();

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    mutation.reset();

    const errors: Partial<Record<CreateField, string>> = {
      username: validateUsername(username),
      email: validateEmail(email),
      full_name: validateFullName(fullName),
      password: validatePassword(password),
    };
    setClientErrors(errors);
    if (Object.values(errors).some(Boolean)) {
      return;
    }
    mutation.mutate(
      {
        username: username.trim(),
        email: email.trim(),
        full_name: fullName.trim(),
        password,
        role,
      },
      {
        onSuccess: (user) => {
          void navigate(`/users/${user.id}`);
        },
      },
    );
  };

  const server = mutation.error
    ? toFormErrors(mutation.error, FIELDS, {
        USERNAME_TAKEN: 'username',
        EMAIL_TAKEN: 'email',
        WEAK_PASSWORD: 'password',
      })
    : { fields: {}, general: null };
  const fieldError = (field: CreateField) => clientErrors[field] ?? server.fields[field];

  return (
    <form onSubmit={submit} noValidate>
      {server.general !== null && <ErrorMessage error={server.general} />}
      {roles.error && <ErrorMessage error={roles.error} />}

      <Field
        label="Username"
        error={fieldError('username')}
        hint="3 to 50 characters: letters, digits, dots, underscores or hyphens."
      >
        {(props) => (
          <input
            {...props}
            name="username"
            autoComplete="off"
            autoCapitalize="none"
            value={username}
            onChange={(event) => {
              setUsername(event.target.value);
            }}
          />
        )}
      </Field>
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
      <Field
        label="Password"
        error={fieldError('password')}
        hint="12 to 128 characters, not a commonly used password, not the username or email."
      >
        {(props) => (
          <input
            {...props}
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        )}
      </Field>
      <Field label="Role" error={fieldError('role')}>
        {(props) => (
          <select
            {...props}
            name="role"
            value={role}
            onChange={(event) => {
              setRole(event.target.value as RoleName);
            }}
          >
            {(roles.data ?? [{ name: role, permissions: [] }]).map(({ name }) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Creating…' : 'Create user'}
      </button>
    </form>
  );
}

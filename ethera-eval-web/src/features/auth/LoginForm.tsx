/**
 * Login form: username and password, submitted through useLogin.
 *
 * Role: the sign-in UI of the login page.
 * Used by: pages/LoginPage.tsx.
 * Depends on: ./use-login, Alert, ErrorMessage, Field, ApiError (code INVALID_CREDENTIALS).
 * Key invariants: wrong username, wrong password and an inactive account all get the same message,
 *   matching the backend's single INVALID_CREDENTIALS answer; do not tell them apart. Submit is
 *   disabled while pending or while a field is empty.
 */
import { useState, type SubmitEvent } from 'react';

import { useLogin } from './use-login';
import { Alert } from '@/components/ui/Alert';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { Field } from '@/components/ui/Field';
import { ApiError } from '@/lib/api/errors';

/**
 * Wrong username, wrong password and an inactive account all get the same
 * answer from the backend, and the same message here.
 */
const INVALID_CREDENTIALS_MESSAGE = 'The username or password is incorrect.';

export function LoginForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const mutation = useLogin();

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    mutation.mutate({ username, password });
  };

  const { error } = mutation;
  const invalidCredentials = error instanceof ApiError && error.code === 'INVALID_CREDENTIALS';

  return (
    <form onSubmit={submit} noValidate>
      {invalidCredentials && (
        <Alert>
          <p className="my-0">{INVALID_CREDENTIALS_MESSAGE}</p>
        </Alert>
      )}
      {error && !invalidCredentials && <ErrorMessage error={error} />}

      <Field label="Username">
        {(props) => (
          <input
            {...props}
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            value={username}
            onChange={(event) => {
              setUsername(event.target.value);
            }}
          />
        )}
      </Field>
      <Field label="Password">
        {(props) => (
          <input
            {...props}
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        )}
      </Field>
      <button
        type="submit"
        disabled={mutation.isPending || username.trim() === '' || password === ''}
      >
        {mutation.isPending ? 'Logging in…' : 'Log in'}
      </button>
    </form>
  );
}

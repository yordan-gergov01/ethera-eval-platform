/**
 * Turns any error from a backend call into a user-facing message plus its request ID.
 *
 * Role: the one place that maps ApiError, NetworkError and unknown errors to text.
 * Used by: features LoginForm, PasswordForm, ProfileForm, CreateUserForm, EditUserForm, UserDetail,
 *   UsersList; routes/RequireAuth.tsx.
 * Depends on: ./Alert, ApiError and NetworkError from lib/api/errors.
 * Key invariants: branches on code and status; PERMISSION_DENIED, 429, 5xx and non-API errors
 *   get fixed text, other 4xx show the backend detail; 429 shows the Retry-After seconds when
 *   given; the request ID is shown whenever the backend supplied one so a failure can be
 *   reported; rendered as plain text only.
 */
import { Alert } from './Alert';
import { ApiError, NetworkError } from '@/lib/api/errors';

function describe(error: unknown): string {
  if (error instanceof NetworkError) {
    return 'The server could not be reached. Check your connection and try again.';
  }
  if (!(error instanceof ApiError)) {
    return 'Something went wrong.';
  }
  if (error.code === 'PERMISSION_DENIED') {
    return 'You are not allowed to do this.';
  }
  if (error.status === 429) {
    return error.retryAfter === undefined
      ? 'Too many requests. Please wait a moment and try again.'
      : `Too many requests. Try again in ${String(error.retryAfter)} seconds.`;
  }
  if (error.status === 503) {
    return 'The service is temporarily unavailable. Please try again later.';
  }
  if (error.status >= 500) {
    return 'Something went wrong on the server. Please try again later.';
  }
  return error.detail;
}

export interface ErrorMessageProps {
  error: unknown;
}

/**
 * Shows an error from a backend call. The request ID identifies the request in
 * the backend logs and is shown so a failure can be reported.
 */
export function ErrorMessage({ error }: ErrorMessageProps) {
  const requestId = error instanceof ApiError ? error.requestId : undefined;

  return (
    <Alert>
      <p className="my-0">{describe(error)}</p>
      {requestId && (
        <p className="mt-1 mb-0 text-xs text-red-700">
          Request ID: <code className="select-all">{requestId}</code>
        </p>
      )}
    </Alert>
  );
}

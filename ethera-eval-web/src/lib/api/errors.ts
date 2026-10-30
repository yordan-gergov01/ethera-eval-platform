/**
 * Error types for backend calls, built from RFC 9457 problem details.
 *
 * Role: ApiError (the backend answered with an error), NetworkError (no answer) and the parsing
 *   helpers.
 * Used by: lib/api/client.ts, lib/api/form-errors.ts, lib/query-client.ts, lib/long-poll.ts,
 *   components/ui/ErrorMessage.tsx, features/auth/LoginForm.tsx, and their tests.
 * Depends on: FieldError and ProblemDetails from ./types; the Retry-After and X-Request-ID headers.
 * Key invariants: branch on `code`, never on `detail` (which is for people); unknown codes are
 *   kept; a body that is not problem details becomes code HTTP_ERROR; Retry-After is read in
 *   seconds only; the body's request_id wins over the X-Request-ID header; the first message per
 *   field wins.
 */
import type { FieldError, ProblemDetails } from './types';

export interface ApiErrorInit {
  status: number;
  /** The backend's error code; unknown codes are kept as they are. */
  code: string;
  title: string;
  detail: string;
  /** Identifies the request in the backend logs; show it for support. */
  requestId?: string | undefined;
  /** Seconds to wait before trying again (429 and 503). */
  retryAfter?: number | undefined;
  /** Validation messages by form field, for example `{ email: '...' }`. */
  fieldErrors?: Readonly<Record<string, string>>;
}

/**
 * An error response from the backend, built from its problem details
 * (RFC 9457). Branch on `code`, never on `detail`, which is for people.
 */
export class ApiError extends Error {
  override name = 'ApiError';
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly requestId: string | undefined;
  readonly retryAfter: number | undefined;
  readonly fieldErrors: Readonly<Record<string, string>>;

  constructor(init: ApiErrorInit) {
    super(init.detail);
    this.status = init.status;
    this.code = init.code;
    this.title = init.title;
    this.detail = init.detail;
    this.requestId = init.requestId;
    this.retryAfter = init.retryAfter;
    this.fieldErrors = init.fieldErrors ?? {};
  }
}

/** The request never got an answer: the backend is unreachable or the connection failed. */
export class NetworkError extends Error {
  override name = 'NetworkError';

  constructor(cause: unknown) {
    super('The server could not be reached.', { cause });
  }
}

/**
 * Maps the backend's field errors to form fields. The first part of the
 * location (`body`, `query`, `path`) is dropped: `body.email` becomes `email`.
 * The first message for a field wins.
 */
export function toFieldErrors(errors: readonly FieldError[] | null | undefined) {
  const result: Record<string, string> = {};
  for (const { field, message } of errors ?? []) {
    const name = field.split('.').slice(1).join('.') || field;
    result[name] ??= message;
  }
  return result;
}

/** Parses a Retry-After header given in seconds (the only form the backend sends). */
export function parseRetryAfter(value: string | null): number | undefined {
  if (value === null || !/^\d+$/.test(value.trim())) {
    return undefined;
  }
  return Number(value.trim());
}

function isProblemDetails(value: unknown): value is ProblemDetails {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const { status, code, detail } = value as Record<string, unknown>;
  return typeof status === 'number' && typeof code === 'string' && typeof detail === 'string';
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

/**
 * Builds an ApiError from a failed response. A body that is not problem
 * details (for example an HTML page from a proxy) gives a generic error
 * based on the HTTP status.
 */
export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  const retryAfter = parseRetryAfter(response.headers.get('Retry-After'));
  const headerRequestId = response.headers.get('X-Request-ID') ?? undefined;
  const body = (response.headers.get('Content-Type') ?? '').includes('json')
    ? await readJson(response)
    : undefined;

  if (isProblemDetails(body)) {
    return new ApiError({
      status: body.status,
      code: body.code,
      title: body.title,
      detail: body.detail,
      requestId: body.request_id ?? headerRequestId,
      retryAfter,
      fieldErrors: toFieldErrors(body.errors),
    });
  }
  return new ApiError({
    status: response.status,
    code: 'HTTP_ERROR',
    title: response.statusText || 'Error',
    detail: `The server answered with status ${String(response.status)}.`,
    requestId: headerRequestId,
    retryAfter,
  });
}

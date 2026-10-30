/**
 * Unit tests for parsing the backend's problem details.
 *
 * Role: proves toFieldErrors, parseRetryAfter and apiErrorFromResponse.
 * Used by: Vitest.
 * Depends on: ./errors.
 * Key invariants: pins that unknown codes are kept and that a body which is not problem details
 *   falls back to a generic error.
 */
import { describe, expect, it } from 'vitest';

import { ApiError, apiErrorFromResponse, parseRetryAfter, toFieldErrors } from './errors';

function problem(body: Record<string, unknown>, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status: typeof body.status === 'number' ? body.status : 500,
    headers: { 'Content-Type': 'application/problem+json', ...headers },
  });
}

describe('toFieldErrors', () => {
  it('drops the location prefix and keeps the first message per field', () => {
    expect(
      toFieldErrors([
        { field: 'body.email', message: 'Invalid email', type: 'value_error' },
        { field: 'body.email', message: 'Second message', type: 'value_error' },
        { field: 'query.limit', message: 'Too large', type: 'less_than_equal' },
        { field: 'body.address.city', message: 'Required', type: 'missing' },
        { field: 'body', message: 'Invalid body', type: 'model_type' },
      ]),
    ).toEqual({
      email: 'Invalid email',
      limit: 'Too large',
      'address.city': 'Required',
      body: 'Invalid body',
    });
  });

  it('accepts missing errors', () => {
    expect(toFieldErrors(undefined)).toEqual({});
    expect(toFieldErrors(null)).toEqual({});
  });
});

describe('parseRetryAfter', () => {
  it.each([
    ['1', 1],
    [' 30 ', 30],
    [null, undefined],
    ['', undefined],
    ['-1', undefined],
    ['1.5', undefined],
    ['Wed, 21 Oct 2026 07:28:00 GMT', undefined],
  ])('parses %j as %j', (input, expected) => {
    expect(parseRetryAfter(input)).toBe(expected);
  });
});

describe('apiErrorFromResponse', () => {
  it('builds the error from problem details', async () => {
    const error = await apiErrorFromResponse(
      problem(
        {
          type: 'about:blank',
          title: 'Unprocessable Content',
          status: 422,
          detail: 'The request is invalid.',
          instance: '/api/v1/users',
          code: 'VALIDATION_FAILED',
          request_id: 'req-1',
          errors: [{ field: 'body.username', message: 'Too short', type: 'string_too_short' }],
        },
        { 'X-Request-ID': 'req-header' },
      ),
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      code: 'VALIDATION_FAILED',
      title: 'Unprocessable Content',
      detail: 'The request is invalid.',
      message: 'The request is invalid.',
      requestId: 'req-1',
      retryAfter: undefined,
      fieldErrors: { username: 'Too short' },
    });
  });

  it('reads Retry-After and falls back to the X-Request-ID header', async () => {
    const error = await apiErrorFromResponse(
      problem(
        {
          title: 'Too Many Requests',
          status: 429,
          detail: 'Slow down.',
          code: 'TOO_MANY_CONCURRENT_POLLS',
        },
        { 'Retry-After': '1', 'X-Request-ID': 'req-header' },
      ),
    );

    expect(error).toMatchObject({
      code: 'TOO_MANY_CONCURRENT_POLLS',
      retryAfter: 1,
      requestId: 'req-header',
      fieldErrors: {},
    });
  });

  it('keeps unknown codes', async () => {
    const error = await apiErrorFromResponse(
      problem({ title: 'Conflict', status: 409, detail: 'No.', code: 'SOMETHING_NEW' }),
    );
    expect(error.code).toBe('SOMETHING_NEW');
  });

  it('falls back to a generic error for a body that is not problem details', async () => {
    const error = await apiErrorFromResponse(
      new Response('<html>Bad Gateway</html>', {
        status: 502,
        statusText: 'Bad Gateway',
        headers: { 'Content-Type': 'text/html' },
      }),
    );

    expect(error).toMatchObject({
      status: 502,
      code: 'HTTP_ERROR',
      title: 'Bad Gateway',
      detail: 'The server answered with status 502.',
      requestId: undefined,
    });
  });

  it('falls back when a JSON body cannot be parsed', async () => {
    const error = await apiErrorFromResponse(
      new Response('{not json', { status: 500, headers: { 'Content-Type': 'application/json' } }),
    );
    expect(error).toMatchObject({ status: 500, code: 'HTTP_ERROR' });
  });
});

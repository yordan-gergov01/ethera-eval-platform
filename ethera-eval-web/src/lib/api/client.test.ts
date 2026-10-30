/**
 * Unit tests for the fetch-based API client.
 *
 * Role: proves headers, bodies, 204 handling, error wrapping and the 401/403 callbacks.
 * Used by: Vitest.
 * Depends on: ./client, ./errors, vi.fn standing in for fetch.
 * Key invariants: pins "does not report a 401 on the login request", "does not report a 401 when no
 *   token was sent" and "passes an abort through unchanged"; these behaviours are deliberate.
 */
import { describe, expect, it, vi } from 'vitest';

import { createApiClient } from './client';
import { ApiError, NetworkError } from './errors';

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function problem(status: number, code: string) {
  return new Response(JSON.stringify({ title: 'Error', status, detail: 'Failed.', code }), {
    status,
    headers: { 'Content-Type': 'application/problem+json' },
  });
}

function setup(respond: () => Promise<Response>, token: string | null = 'tkn') {
  const fetchMock = vi.fn<typeof fetch>(respond);
  const onUnauthorized = vi.fn();
  const onForbidden = vi.fn();
  const client = createApiClient({
    baseUrl: () => 'http://backend:8000',
    getToken: () => token,
    onUnauthorized,
    onForbidden,
    fetch: fetchMock,
  });
  const lastCall = () => {
    const call = fetchMock.mock.lastCall;
    if (!call) {
      throw new Error('fetch was not called');
    }
    const [url, init = {}] = call;
    const href = typeof url === 'string' ? url : url instanceof URL ? url.href : url.url;
    return { url: href, init, headers: new Headers(init.headers) };
  };
  return { client, onUnauthorized, onForbidden, lastCall };
}

describe('createApiClient', () => {
  it('sends a GET with the bearer token and query parameters, and returns the body', async () => {
    const { client, lastCall } = setup(() => Promise.resolve(json({ items: [] })));

    const result = await client.get<{ items: unknown[] }>('/api/v1/users', {
      query: { limit: 10, offset: 0, unused: undefined },
    });

    expect(result).toEqual({ items: [] });
    const { url, init, headers } = lastCall();
    expect(url).toBe('http://backend:8000/api/v1/users?limit=10&offset=0');
    expect(init.method).toBe('GET');
    expect(init.body).toBeUndefined();
    expect(headers.get('Authorization')).toBe('Bearer tkn');
    expect(headers.get('Accept')).toBe('application/json');
  });

  it('sends a JSON body', async () => {
    const { client, lastCall } = setup(() => Promise.resolve(json({ id: '1' }, 201)));

    await client.post('/api/v1/users', { json: { username: 'alice' } });

    const { init, headers } = lastCall();
    expect(init.method).toBe('POST');
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(init.body).toBe('{"username":"alice"}');
  });

  it('sends a form body without a token when auth is false', async () => {
    const { client, lastCall } = setup(() => Promise.resolve(json({ access_token: 'x' })));

    await client.post('/api/v1/auth/login', {
      form: { username: 'admin', password: 'p&ss word' },
      auth: false,
    });

    const { init, headers } = lastCall();
    expect(headers.get('Content-Type')).toBe('application/x-www-form-urlencoded');
    expect(init.body).toBe('username=admin&password=p%26ss+word');
    expect(headers.has('Authorization')).toBe(false);
  });

  it('omits the Authorization header when there is no token', async () => {
    const { client, lastCall } = setup(() => Promise.resolve(json({})), null);
    await client.get('/api/v1/users/me');
    expect(lastCall().headers.has('Authorization')).toBe(false);
  });

  it('returns undefined for 204', async () => {
    const { client } = setup(() => Promise.resolve(new Response(null, { status: 204 })));
    await expect(client.post('/api/v1/auth/logout')).resolves.toBeUndefined();
  });

  it('throws an ApiError for an error response', async () => {
    const { client, onUnauthorized } = setup(() =>
      Promise.resolve(problem(403, 'PERMISSION_DENIED')),
    );

    const error = await client.get('/api/v1/users').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, code: 'PERMISSION_DENIED' });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('reports a 401 on a request that carried a token', async () => {
    const { client, onUnauthorized } = setup(() => Promise.resolve(problem(401, 'INVALID_TOKEN')));

    await expect(client.get('/api/v1/users/me')).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it('does not report a 401 on the login request', async () => {
    const { client, onUnauthorized } = setup(() =>
      Promise.resolve(problem(401, 'INVALID_CREDENTIALS')),
    );

    await expect(
      client.post('/api/v1/auth/login', { form: { username: 'a', password: 'b' }, auth: false }),
    ).rejects.toMatchObject({ status: 401, code: 'INVALID_CREDENTIALS' });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('does not report a 401 when no token was sent', async () => {
    const { client, onUnauthorized } = setup(
      () => Promise.resolve(problem(401, 'AUTHENTICATION_FAILED')),
      null,
    );
    await expect(client.get('/api/v1/users/me')).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('reports a 403 PERMISSION_DENIED', async () => {
    const { client, onForbidden, onUnauthorized } = setup(() =>
      Promise.resolve(problem(403, 'PERMISSION_DENIED')),
    );

    await expect(
      client.patch('/api/v1/users/me', { json: { full_name: 'x' } }),
    ).rejects.toMatchObject({
      status: 403,
    });
    expect(onForbidden).toHaveBeenCalledOnce();
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('does not report a 403 when the request opts out', async () => {
    const { client, onForbidden } = setup(() => Promise.resolve(problem(403, 'PERMISSION_DENIED')));

    await expect(client.get('/api/v1/users/me', { reportForbidden: false })).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(onForbidden).not.toHaveBeenCalled();
  });

  it('does not report other 403 codes', async () => {
    const { client, onForbidden } = setup(() =>
      Promise.resolve(problem(403, 'SELF_MODIFICATION_FORBIDDEN')),
    );

    await expect(client.patch('/api/v1/users/1', { json: {} })).rejects.toBeInstanceOf(ApiError);
    expect(onForbidden).not.toHaveBeenCalled();
  });

  it('wraps connection failures in a NetworkError', async () => {
    const { client } = setup(() => Promise.reject(new TypeError('Failed to fetch')));

    const error = await client.get('/api/v1/users/me').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NetworkError);
    expect((error as NetworkError).cause).toBeInstanceOf(TypeError);
  });

  it('passes an abort through unchanged', async () => {
    const controller = new AbortController();
    const abortError = new DOMException('The operation was aborted.', 'AbortError');
    const { client, lastCall } = setup(() => {
      controller.abort();
      return Promise.reject(abortError);
    });

    await expect(client.get('/api/v1/users/1', { signal: controller.signal })).rejects.toBe(
      abortError,
    );
    expect(lastCall().init.signal).toBe(controller.signal);
  });
});

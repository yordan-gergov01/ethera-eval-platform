/**
 * Unit tests for the runtime backend URL validation.
 *
 * Role: proves parseBackendUrl accepts only http(s) origins and loadRuntimeConfig fails without
 *   /config.js.
 * Used by: Vitest.
 * Depends on: ./runtime-config.
 * Key invariants: the rejected cases (credentials, path, query, fragment, non-http(s) schemes) are
 *   deliberate: the backend URL must be a bare origin (template_web D-004).
 */
import { describe, expect, it } from 'vitest';

import { ConfigError, loadRuntimeConfig, parseBackendUrl } from './runtime-config';

describe('parseBackendUrl', () => {
  it.each([
    ['http://localhost:8000', 'http://localhost:8000'],
    ['http://localhost:8000/', 'http://localhost:8000'],
    ['  https://api.example.com  ', 'https://api.example.com'],
    ['HTTPS://API.EXAMPLE.COM:443', 'https://api.example.com'],
  ])('accepts %j as %j', (input, expected) => {
    expect(parseBackendUrl(input)).toBe(expected);
  });

  it.each([
    undefined,
    null,
    42,
    '',
    '   ',
    'localhost:8000',
    'not a url',
    'ftp://example.com',
    'javascript:alert(1)',
    'http://user:secret@example.com',
    'http://example.com/api',
    'http://example.com/?x=1',
    'http://example.com/#top',
  ])('rejects %j', (input) => {
    expect(() => parseBackendUrl(input)).toThrow(ConfigError);
  });
});

describe('loadRuntimeConfig', () => {
  it('returns the validated backend URL', () => {
    expect(loadRuntimeConfig({ backendUrl: 'http://localhost:8000/' })).toEqual({
      backendUrl: 'http://localhost:8000',
    });
  });

  it('fails when /config.js was not loaded', () => {
    expect(() => loadRuntimeConfig(undefined)).toThrow(ConfigError);
  });
});

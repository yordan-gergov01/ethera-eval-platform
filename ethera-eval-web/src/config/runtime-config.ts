/**
 * Reads and validates the backend URL from the runtime configuration (/config.js).
 *
 * Role: the app's only source of the backend origin, validated so a bad config shows an error, not
 *   a blank page.
 * Used by: src/main.tsx (startup check), lib/api/http.ts (base URL of every request),
 *   runtime-config.test.ts.
 * Depends on: window.__APP_CONFIG__ set by /config.js (typed in types/app-config.d.ts), the URL
 *   API.
 * Key invariants: accepts only http/https origins without credentials, path, query or fragment;
 *   returns the origin without a trailing slash; read once and cached per page; failures throw
 *   ConfigError, which main.tsx renders (template_web D-004).
 */
export interface RuntimeConfig {
  /** Origin of the backend, for example `http://localhost:8000`, without a trailing slash. */
  backendUrl: string;
}

export class ConfigError extends Error {
  override name = 'ConfigError';
}

/**
 * Validates the configured backend URL: http or https, no credentials, path,
 * query or fragment. Returns the origin, which never ends with a slash.
 */
export function parseBackendUrl(value: unknown): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new ConfigError('The backend URL is not configured.');
  }
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new ConfigError('The backend URL is not a valid URL.');
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new ConfigError('The backend URL must use http or https.');
  }
  if (url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new ConfigError('The backend URL must be an origin only, for example http://host:8000.');
  }
  return url.origin;
}

export function loadRuntimeConfig(source: Window['__APP_CONFIG__']): RuntimeConfig {
  if (!source) {
    throw new ConfigError('The runtime configuration (/config.js) was not loaded.');
  }
  return { backendUrl: parseBackendUrl(source.backendUrl) };
}

let cached: RuntimeConfig | undefined;

/** The validated runtime configuration of this page, read once. Throws ConfigError. */
export function getRuntimeConfig(): RuntimeConfig {
  cached ??= loadRuntimeConfig(window.__APP_CONFIG__);
  return cached;
}

/**
 * Global type of window.__APP_CONFIG__, the runtime configuration.
 *
 * Role: types what /config.js sets: written when the container starts and served by the Vite dev
 *   server locally, loaded before the application bundle.
 * Used by: config/runtime-config.ts (Window['__APP_CONFIG__'] and window.__APP_CONFIG__); an
 *   ambient declaration, never imported.
 * Depends on: /config.js loaded by index.html (template_web D-004).
 * Key invariants: backendUrl is `unknown` on purpose: the value is untrusted until parseBackendUrl
 *   validates it; the file must stay a script (no import or export) so the Window augmentation
 *   stays global.
 */
interface Window {
  __APP_CONFIG__?: {
    backendUrl?: unknown;
  };
}

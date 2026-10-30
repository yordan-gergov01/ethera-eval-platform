/**
 * Browser entry point: validates the runtime configuration and mounts the app.
 *
 * Role: renders <App /> into #root, or a configuration error page when /config.js is missing or
 *   invalid.
 * Used by: index.html (loaded as a module after /config.js).
 * Depends on: react-dom/client, ./App, getRuntimeConfig and ConfigError, ./assets/index.css.
 * Key invariants: a ConfigError shows "Configuration error" instead of a blank page (template_web
 *   D-004); any other error is rethrown; StrictMode stays on.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App.tsx';
import { ConfigError, getRuntimeConfig } from '@/config/runtime-config';
import './assets/index.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}
const root = createRoot(rootElement);

try {
  getRuntimeConfig();
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
} catch (error) {
  if (!(error instanceof ConfigError)) {
    throw error;
  }
  root.render(
    <main>
      <h1>Configuration error</h1>
      <p>{error.message}</p>
    </main>,
  );
}

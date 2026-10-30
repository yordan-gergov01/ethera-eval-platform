import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { loadEnv, type Plugin, type PreviewServer, type ViteDevServer } from 'vite';
import { defineConfig } from 'vitest/config';

// The backend's CORS allows http://localhost:3000, so the dev server must use
// exactly that origin and fail instead of moving to another port.
const devServer = { host: 'localhost', port: 3000, strictPort: true };

const DEFAULT_BACKEND_URL = 'http://localhost:8000';

function checkBackendUrl(value: string): string {
  const url = URL.canParse(value) ? new URL(value) : undefined;
  if (!url || (url.protocol !== 'http:' && url.protocol !== 'https:')) {
    throw new Error(`BACKEND_URL must be an http(s) URL, got "${value}"`);
  }
  return url.origin;
}

/**
 * Serves /config.js in development and preview, the local equivalent of the
 * file the container entrypoint writes from BACKEND_URL. Production builds do
 * not contain it.
 */
function runtimeConfig(backendUrl: string): Plugin {
  const body = `window.__APP_CONFIG__ = ${JSON.stringify({ backendUrl })};\n`;
  const serve = (server: ViteDevServer | PreviewServer) => {
    server.middlewares.use('/config.js', (_req, res) => {
      res.setHeader('Content-Type', 'text/javascript; charset=utf-8');
      res.setHeader('Cache-Control', 'no-store');
      res.end(body);
    });
  };
  return { name: 'runtime-config', configureServer: serve, configurePreviewServer: serve };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendUrl = checkBackendUrl(env.BACKEND_URL ?? DEFAULT_BACKEND_URL);

  return {
    plugins: [react(), tailwindcss(), runtimeConfig(backendUrl)],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: devServer,
    preview: devServer,
    build: {
      sourcemap: false,
    },
    test: {
      include: ['src/**/*.test.{ts,tsx}'],
      environment: 'node',
    },
  };
});

// Saves the backend's OpenAPI document to openapi/openapi.json, pretty-printed
// so contract changes show up as readable diffs. Reads BACKEND_URL from the
// environment or .env (default http://localhost:8000).
import { writeFile } from 'node:fs/promises';

const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000';
const source = new URL('/openapi.json', backendUrl);

const response = await fetch(source);
if (!response.ok) {
  throw new Error(`GET ${source.href} answered ${String(response.status)}`);
}
const document = await response.json();
await writeFile(
  new URL('../openapi/openapi.json', import.meta.url),
  `${JSON.stringify(document, null, 2)}\n`,
);
process.stdout.write(`Saved the OpenAPI document from ${source.href}\n`);

# Decision log

## Open questions from the brief

### D-001: Frontend framework and application state

- **Context:** The brief leaves the frontend framework open. The app is a small single-page client that proves the backend works: forms, a paged list, permission-driven navigation and a long-polled result. It is served as static files and must be easy to read and maintain.
- **Options considered:** React with Vite and TypeScript - widely known, builds to static files, but routing and data fetching are separate libraries; Next.js - routing and data fetching built in, but a server runtime and server rendering the app does not need; Vue or Svelte with Vite - smaller, but less widely known; no framework - no dependencies, but routing, state and rendering written by hand. For state: a global store such as Redux or Zustand - one place for everything, but it duplicates what a server-state cache already holds; TanStack Query for server data and a React context for the session.
- **Decision:** React with Vite and strict TypeScript, React Router for routes and permission guards, TanStack Query for all data read from the backend, and a React context for the session (token, current user, `can()`). No global store and no UI kit, only a few small components of our own. The code is organised by feature (auth, profile, users, prompts, llm-model): features never import each other, pages compose them, and ESLint enforces these import rules.
- **Consequences:** The build output is static files served by nginx, so one image fits every environment. Server data has a single source, with caching and invalidation after changes. Each feature can be read on its own.
- **With more time:** Component tests with Testing Library and end-to-end tests against a running backend.

### D-002: Dependency management, linting and formatting

- **Context:** The brief leaves open how dependencies are managed and how code quality is checked. Builds must be reproducible, and the checks must give the same result on every machine.
- **Options considered:** Version ranges with a lockfile - installs are pinned, but `npm install` can move direct dependencies; exact versions with a lockfile installed by `npm ci` - every version visible in `package.json`, updates are deliberate. TypeScript 7 - the newest, but typescript-eslint and openapi-typescript do not support it yet; TypeScript 5.9 - supported by every tool in use. A Git hook tool such as husky - checks run automatically, but one more dependency, and hooks can be skipped; a single `npm run check` script.
- **Decision:** Exact versions and the committed lockfile, installed with `npm ci` in the image; Node 24 LTS through `.nvmrc` and `engines`; TypeScript 5.9 in strict mode. ESLint (strict type-checked rules, React hooks rules, import boundaries), Prettier and Vitest run together through `npm run check`, which must pass before every commit.
- **Consequences:** The same commit installs the same packages everywhere, and dependency updates appear as reviewable diffs. Running the checks before a commit is a habit, not enforced by a hook. TypeScript stays one major version behind until the tools support 7.
- **With more time:** A CI pipeline that runs `npm run check` and builds the image on every push, automated dependency updates with a vulnerability scan, and TypeScript 7 once typescript-eslint supports it.

### D-003: Where the browser keeps the token, and how logout works

- **Context:** The brief leaves open where the frontend keeps the access token and what logging out does. The choice decides what a cross-site scripting flaw could steal, whether a reload keeps the session, and how a session ends. The backend issues 30-minute bearer tokens and revokes all of a user's tokens at once (template_core D-006).
- **Options considered:** Memory only - nothing persists for a script to read later, but every reload or new tab means logging in again; `localStorage` - survives reloads and tabs, but stays on the device indefinitely and is readable by any script on the origin; `sessionStorage` - survives a reload, ends with the tab, equally readable by scripts; an HttpOnly cookie - not readable by scripts, but needs cookie support, CSRF protection and credentialed CORS on the backend.
- **Decision:** The token and its expiry time are kept in `sessionStorage`. The exposure to scripts is limited by a strict Content-Security-Policy without inline scripts, by rendering model output as plain text, and by the short token lifetime. The session ends 30 seconds before the token expires, on any 401 to a request that carried the token, and on logout. Logout calls `POST /api/v1/auth/logout`, which ends every session of the user, and then clears the token and all cached data whatever the answer. After a password change the local session is cleared the same way.
- **Consequences:** A reload keeps the session, and closing the tab ends it. Each tab signs in on its own; logging out in one tab ends the sessions of the others on the backend, and they notice on their next request. A script injected into the page could still read the token while it is valid, which the CSP and plain-text rendering are there to prevent.
- **With more time:** Cookie-based sessions with refresh tokens, a stretch goal in the brief: an HttpOnly, SameSite cookie with refresh tokens and per-session revocation, together with the backend change it needs.

### D-004: How the frontend finds the backend in each environment

- **Context:** The brief leaves open how the frontend container learns the backend URL. Values that Vite builds into the bundle are fixed at build time, so each environment would need its own image.
- **Options considered:** A build-time variable - simple, but one image per environment and a rebuild for every URL change; the frontend server as a reverse proxy to the backend - same-origin calls without CORS, but the frontend container then needs a network path to the backend and becomes part of the request path; a runtime configuration file written when the container starts - one image everywhere, and the browser calls the backend directly.
- **Decision:** `index.html` loads `/config.js` before the application. The container's entrypoint writes it from `BACKEND_URL` (`window.__APP_CONFIG__ = { backendUrl: "..." }`) and refuses to start when the value is not an http(s) URL; the app validates it again and shows a configuration error instead of a blank page. In development, the Vite dev server serves the same file from `BACKEND_URL`. The browser calls the backend directly, and the backend's CORS allow-list contains the frontend's origin.
- **Consequences:** The same image runs in every environment, and changing the backend URL takes a restart, not a rebuild. The frontend container needs no network connection to the backend. The backend must list each frontend origin in `CORS_ALLOWED_ORIGINS`, and the CSP's `connect-src` must name the backend origin.
- **With more time:** Serving the frontend and the API under one origin behind a shared reverse proxy, which would remove CORS from the setup.

### D-006: How the frontend receives an asynchronous result

- **Context:** An answer from the LLM service arrives seconds after the prompt is submitted. The backend answers `POST /api/v1/prompts` with 202 and offers long polling (template_core D-009); the brief leaves open how the browser uses it. Each waiting poll holds a request on the backend, at most three per user and replica may wait at once, and every poll counts against the rate limit.
- **Options considered:** Short polling at a fixed interval - simple, but slow or wasteful and harder on the rate limit; long polling one request at a time - an answer arrives as soon as it is stored, with one request per 25 seconds while waiting; parallel or overlapping polls - no gain, and they run into the concurrency limit; server-sent events or WebSockets - push without polling, but the backend does not offer them.
- **Decision:** After the 202 the page long-polls `GET /api/v1/prompts/{id}?wait_seconds=25`, one request at a time, until the job is completed or failed. A 429 waits for `Retry-After`; network errors and 5xx answers back off 1, 2, 4 and 8 seconds, then 10, or follow `Retry-After` when given, and the backoff resets after any answer. Other errors stop polling and offer to check again. Polling is cancelled when the job finishes, when the page is left and before a new prompt starts. The answer is shown as plain text together with the model that produced it, and a failed job shows a message for its error code.
- **Consequences:** Answers appear within moments without extra infrastructure or long-lived connections, and the client never exceeds the backend's limits by itself. Leaving the page ends the wait; the job still completes on the backend, but this page does not show it again.
- **With more time:** A list of the user's recent prompts so an answer can be found after leaving the page, and server-sent events if the backend adds them.

## Additional decisions

### D-005: API types generated from the backend's OpenAPI document

- **Context:** The frontend depends on the shapes of every request and response. Types written by hand drift away from the backend unnoticed.
- **Options considered:** Hand-written types - no tooling, but nothing shows when the contract changes; openapi-typescript with committed output - types only, no runtime code, and the diff shows every contract change; a generated client such as openapi-fetch - typed calls as well, but its own error and retry model next to the session and problem-details handling the app needs anyway; runtime validation with a schema library - catches bad responses, but more code and a second definition of each type.
- **Decision:** `npm run api:snapshot` saves the backend's `openapi.json` to `openapi/openapi.json`, and `npm run api:types` generates `src/lib/api/schema.gen.ts` with openapi-typescript. Both are committed and excluded from linting and formatting. Only `src/lib/api/types.ts` imports the generated file; it gives the app short names and narrows the PATCH bodies to fields without null, because the backend rejects explicit nulls although its schema allows them. Calls go through the app's own small fetch client.
- **Consequences:** A contract change shows up as a diff in the snapshot and as type errors where the app uses the changed fields. Responses are trusted to match the contract at run time. Regenerating is a manual step against a running backend.
- **With more time:** A CI check that compares the committed snapshot with the backend's current document.

### D-007: Styling approach

- **Context:** The brief does not assess styling, but the app is demonstrated and must stay readable. The production image will send a strict Content-Security-Policy (`style-src 'self'`), so styles must come from a stylesheet on the same origin, not from inline styles or styles injected at run time.
- **Options considered:** Plain global CSS - no tooling, but naming and reuse are by convention only and the file grows with each screen; CSS modules - scoped class names built into Vite, but every component needs its own file and shared patterns are copied; Tailwind CSS through its Vite plugin - utility classes in the markup and one static CSS file at build time; a component library - fast, but a large dependency and its own look, which the brief does not ask for.
- **Decision:** Tailwind CSS v4 through the official Vite plugin. Native elements (forms, buttons, tables, headings) and a visible focus outline are styled once in a base layer; five shared classes cover patterns used across features, and any further shared pattern becomes a component in `components/ui/` instead of another class. Components that own their layout use utility classes, and Prettier sorts them. There is no component library and no dark mode, and ESLint rejects inline `style` attributes and `<style>` elements. The production build emits one static CSS file, which the CSP allows.
- **Consequences:** Styling stays close to the markup and consistent across screens, with visible focus states for keyboard users and a layout that holds at phone width. Class lists make some JSX longer, and Tailwind is one more build dependency.
- **With more time:** Shared design tokens (colours, spacing) documented for other projects started from this skeleton.

## What I would change with more time

- End-to-end tests in a browser against template_core running in Docker, run together with `npm run check` and the image build in a CI pipeline.
- Cookie-based sessions with refresh tokens instead of a token in `sessionStorage` (D-003), which needs a backend change.
- The frontend and the API behind one reverse proxy with TLS: one origin without CORS, and HSTS.
- Reporting of Content-Security-Policy violations and client errors, so problems in the browser reach the logs.

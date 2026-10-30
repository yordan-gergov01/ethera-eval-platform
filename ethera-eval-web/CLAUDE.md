# ethera-eval-web — what differs here

The repository `CLAUDE.md` and `.claude/rules/` apply in full. Template conventions:
`docs/reference/TEMPLATE_CONVENTIONS.md` (template_web section); this project's own template
decisions: `docs/DECISIONS.md` (template_web D-001…D-007).

- Check before every handover: `npm ci && npm run check && npm run build`.
- Every `src/` file opens with the `/** Role / Used by / Depends on / Key invariants */`
  header; `src/test/file-headers.test.ts` enforces it (only `schema.gen.ts` is exempt).
- One feature per backend module (`src/features/<module-kebab>/`); features never import each
  other (ESLint `FEATURES`); pages compose features; one `PROTECTED_PAGES` entry per page.
- All server data through TanStack Query; API types only through `src/lib/api/types.ts`,
  regenerated with `npm run api:snapshot && npm run api:types` against a running backend.
- Long polling uses `pollUntil` in `src/lib/long-poll.ts` (D-006).
- Every enum shown to users goes through a `Record<Value, Label>` map.
- Model output, Golden text and product answers render as plain text only; no inline styles
  (CSP).

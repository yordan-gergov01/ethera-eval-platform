# Privacy

Source: Bible Part III "GDPR / privacy", generalised. This PoC holds no real client data: all
Goldens, documents and products are fictional seed data. The rules still apply, so the code is
ready for real data.

## Checklist for every change touching data

- Scoped to its client (see `database.md`, C5 / D-014)?
- Reached by the erasure cascade (user deactivation/anonymisation; client removal)?
- Derived data traceable to its source (Trial → Golden → Dataset version)?
- Retention defined?
- Audit-logged if it exposes personal data?
- Nothing personal sent to any model provider (in the PoC there are none; the rule binds the
  production path).

## Personal data in this system

- Personal: user accounts (username, email, full name), notification recipients, IP addresses
  in audit rows.
- Not personal by construction: Golden inputs and outputs of the seeded demo. Real Goldens in
  production may contain customer text, so Golden content is treated as personal-data-class:
  never logged, never in audit details, never in metrics labels.

## Outward actions

Human-triggered over automatic: a Notification asks a human; the Slack channel is off by
default; 202 means accepted, never delivered.

## Mechanical checks

- `tests/integration/test_never_log.py` — drives real flows and asserts no forbidden field
  (emails, names, passwords, tokens, Golden text, query strings) reaches the logs.
- Audit-detail guard (with the audit table): details contain IDs and field names only.

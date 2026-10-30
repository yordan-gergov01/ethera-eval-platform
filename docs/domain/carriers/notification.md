# Carrier: notification

Constrains Notifications, channels and the weekly digest.

## Invariants

| ID | Rule | Status |
|---|---|---|
| INV-NTF-01 | A Notification is raised only when a human decision is needed: a switch or discuss Recommendation, a failed gate, a deprecation within 30 days. Everything else goes to the digest. | accepted |
| INV-NTF-02 | Every Notification links its evidence (Comparison, Model Change, Eval Runs) and carries quality, cost and latency deltas and the reason. | accepted (brief §6.7) |
| INV-NTF-03 | Channels: in-app inbox and logs always; Slack incoming webhook only when `SLACK_WEBHOOK_URL` is set; no URL is ever committed. | accepted |
| INV-NTF-04 | Marking a Notification as handled writes an audit row. | accepted (brief §7.7) |
| INV-NTF-05 | A channel delivery failure never loses the in-app Notification. | proposed |

## Events (candidates)

- `NotificationRaised` — consumer: the channels (inbox, log, Slack). Proposed.

## Open questions

- **OQ-NTF-01**: Digest cadence and timezone in the fixture clock (weekly — which day?).
  Decides: owner at slice 006.
- **OQ-NTF-02**: Who receives a Notification — every user with a permission, or the
  Product's owners? Decides: owner at slice 006.

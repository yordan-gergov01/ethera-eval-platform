"""The PostgreSQL notification channel on which finished jobs are announced.

Role: names the channel. The transaction that makes a job terminal also sends
  `NOTIFY job_events, '<job id>'`, so every backend replica learns about it the moment it is
  committed.
Used by: `backend.core.job_waiter` (listens on it); the integration tests of the waiter and of
  long polling send on it.
Depends on: nothing.
Key invariants: part of the generic job machinery kept for slice 003; no production code sends
  on the channel yet (D-006). The payload is the job ID as text.
"""

JOB_EVENTS_CHANNEL = "job_events"
